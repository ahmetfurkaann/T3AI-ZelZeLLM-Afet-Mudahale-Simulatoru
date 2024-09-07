import random
import networkx as nx
import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.offsetbox import AnnotationBbox, TextArea
from enum import Enum
import math
import json
import requests
from pydantic import BaseModel
from typing import List
import logging
import matplotlib.colors as mcolors
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, QLabel, QComboBox
from PyQt5.QtCore import QTimer
import sys
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# API çağrısı için gerekli yapılar
chat_model_config = {
    "model": "/home/ubuntu/hackathon_model_2/",
    "temperature": 0.01,
    "top_p": 0.95,
    "max_tokens": 1024,
    "repetition_penalty": 1.1,
    "stop_token_ids": [128001, 128009],
    "skip_special_tokens": True
}

class Choice(BaseModel):
    text: str

class APIResponse(BaseModel):
    choices: List[Choice]

def convert_to_special_format(json_data):
    output = "<|begin_of_text|>"
    for entry in json_data:
        if entry["role"] == "system":
            output += f'<|start_header_id|>system<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'
        elif entry["role"] == "user":
            output += f'\n<|start_header_id|>{entry["role"]}<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'
            if json_data.index(entry) != len(json_data) - 1:
                output += ""
        elif entry["role"] == "assistant":
            output += f'\n<|start_header_id|>{entry["role"]}<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'

    output += "\n<|start_header_id|>assistant<|end_header_id|>"
    return output

def get_priority_from_tweet(tweet):
    try:
        json_data = [
            {"role": "system", "content": "Sen T3AI adında, Türkçe yanıt veren bir yardımcı asistansın. Türkiye'nin ilk büyük Türkçe dil modeli olarak, Baykar Teknoloji ve T3 Vakfı tarafından geliştirildin."},
            {"role": "user", "content": f"""Aşağıdaki örnekleri kullanarak, verilen tweet'in öncelik seviyesini 1 (düşük) ile 4 (kritik) arasında değerlendir:

1 - Yiyecek/Su/Barınma ihtiyacı:
"Enkazdan çıkan kazazedeler için çadır, kıyafet ve gıda ihtiyacı var."
"350 kişi acil su, gıda, battaniye ve çadır yardımı bekliyor."

2 - İlaç/Tıbbi Malzeme ihtiyacı:
"Enkaz altından çıkarılan ailenin ameliyat olması gerekiyor."
"Bölgede acil kan ihtiyacı var, özellikle 0 Rh negatif."

3 - Acil Kurtarma ihtiyacı:
"ADIYAMAN MERKEZ SES VAR: Yavuz Selim Mah. 603. Sok. No:1"
"En az 10 kişi enkaz altında ses veriyorlar."

4 - Kritik Durum:
"Doğum yapmak üzere olan kadın enkaz altında. Kurtarma ekibi yok."
"2 ÇOCUK ENKAZ ALTINDA!! Acil yardım gerekiyor."

Tweet: "{tweet}"

Öncelik seviyesi:"""}
        ]

        special_format_output = convert_to_special_format(json_data)

        payload = json.dumps({
            "model": chat_model_config["model"],
            "prompt": special_format_output,
            "temperature": chat_model_config["temperature"],
            "top_p": chat_model_config["top_p"],
            "max_tokens": chat_model_config["max_tokens"],
            "repetition_penalty": chat_model_config["repetition_penalty"],
            "stop_token_ids": chat_model_config["stop_token_ids"],
            "skip_special_tokens": chat_model_config["skip_special_tokens"]
        })

        headers = {
            'Content-Type': 'application/json',
        }

        response = requests.post("https://inference2.t3ai.org/v1/completions", headers=headers, data=payload, timeout=10)

        if response.status_code == 200:
            result = APIResponse.parse_obj(response.json())
            priority_text = result.choices[0].text.strip()
            priority = int(''.join(filter(str.isdigit, priority_text)))
            return max(1, min(4, priority))
        else:
            print(f"API çağrısı başarısız oldu. Hata kodu: {response.status_code}")
            return random.randint(1, 4)
    except Exception as e:
        print(f"API çağrısı sırasında bir hata oluştu: {e}")
        return random.randint(1, 4)

class PatientType(Enum):
    TRAPPED = 1
    INJURED = 2
    NEEDS_SUPPLY = 3

class PatientStatus(Enum):
    WAITING = 1
    ASSIGNED = 2
    BEING_TREATED = 3
    TREATED = 4

class AgentStatus(Enum):
    IDLE = 1
    EN_ROUTE = 2
    ARRIVED = 3
    TREATING = 4
    COMPLETED = 5

class AgentRole(Enum):
    SEARCH_RESCUE = 1
    MEDICAL = 2
    FOOD_SUPPLY = 3

class Patient:
    def __init__(self, x, y, id, tweet, priority, patient_type):
        self.x = x
        self.y = y
        self.id = id
        self.tweet = tweet
        self.initial_priority = priority
        self.current_priority = priority
        self.status = PatientStatus.WAITING
        self.last_help_time = 0
        self.waiting_time = 0
        self.patient_type = patient_type
        self.assigned_agent = None
        self.treatment_progress = 0  # 0 ile 100 arasında bir değer

    def update(self, current_time):
        if self.status == PatientStatus.WAITING:
            self.waiting_time = current_time - self.last_help_time
            if self.waiting_time > 50:
                self.current_priority = min(4, self.current_priority + 1)
        elif self.status == PatientStatus.BEING_TREATED:
            if self.treatment_progress >= 100:
                self.status = PatientStatus.TREATED
                self.current_priority = max(1, self.current_priority - 1)
            else:
                self.treatment_progress += 1  # Her adımda %1 ilerle

    def interrupt_treatment(self):
        self.status = PatientStatus.WAITING
        self.assigned_agent = None
        self.treatment_progress = 0
        self.last_help_time = 0

class Agent:
    def __init__(self, x, y, id, role):
        self.x = x
        self.y = y
        self.id = id
        self.status = AgentStatus.IDLE
        self.target = None
        self.role = role
        self.speed = 0.1  # Birim: birim/saniye
        self.treatment_time = {
            AgentRole.SEARCH_RESCUE: 300,  # 5 dakika
            AgentRole.MEDICAL: 600,        # 10 dakika
            AgentRole.FOOD_SUPPLY: 180     # 3 dakika
        }
        self.treatment_start_time = 0
        self.treatment_efficiency = {
            AgentRole.SEARCH_RESCUE: 2,
            AgentRole.MEDICAL: 3,
            AgentRole.FOOD_SUPPLY: 1
        }

    def can_help(self, patient):
        if self.role == AgentRole.SEARCH_RESCUE:
            return patient.patient_type == PatientType.TRAPPED
        elif self.role == AgentRole.MEDICAL:
            return patient.patient_type == PatientType.INJURED
        elif self.role == AgentRole.FOOD_SUPPLY:
            return patient.patient_type == PatientType.NEEDS_SUPPLY
        return False

    def calculate_travel_time(self, target_x, target_y):
        distance = math.sqrt((self.x - target_x)**2 + (self.y - target_y)**2)
        return distance / self.speed

    def update(self, current_time):
        if self.status == AgentStatus.EN_ROUTE:
            if self.target:
                dx = self.target.x - self.x
                dy = self.target.y - self.y
                distance = math.sqrt(dx**2 + dy**2)
                if distance <= self.speed:
                    self.x, self.y = self.target.x, self.target.y
                    self.status = AgentStatus.ARRIVED
                else:
                    self.x += (dx / distance) * self.speed
                    self.y += (dy / distance) * self.speed
        elif self.status == AgentStatus.TREATING:
            if self.target:
                self.target.treatment_progress += self.treatment_efficiency[self.role]
                if self.target.treatment_progress >= 100:
                    self.status = AgentStatus.COMPLETED
                    self.target.status = PatientStatus.TREATED

def get_nearest_node(G, x, y):
    nodes = list(G.nodes(data=True))
    return min(nodes, key=lambda n: (n[1]['x'] - x)**2 + (n[1]['y'] - y)**2)[0]

def load_tweets(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"Dosya bulunamadı: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Dosya geçerli bir JSON formatında değil: {file_path}")
        return []
    except Exception as e:
        print(f"Dosya yüklenirken bir hata oluştu: {e}")
        return []

class Simulation:
    def __init__(self, G, num_patients, tweets_file, num_agents):
        self.G = G
        self.tweets = load_tweets(tweets_file)
        self.patients = self.generate_patients(num_patients)
        self.agents = self.generate_agents(num_agents)
        self.current_time = 0
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(filename='simulation.log', level=logging.INFO,
                            format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

    def generate_patients(self, num_patients):
        patients = []
        nodes = list(self.G.nodes(data=True))
        used_tweet_indices = set()
        for i in range(num_patients):
            node = random.choice(nodes)
            x, y = node[1]['x'], node[1]['y']
            tweet = self.get_random_tweet(used_tweet_indices)
            priority = get_priority_from_tweet(tweet)
            patient_type = random.choice(list(PatientType))
            patients.append(Patient(x, y, f"P{i+1}", tweet, priority, patient_type))
        return patients

    def get_random_tweet(self, used_tweet_indices):
        available_indices = [i for i in range(len(self.tweets)) if i not in used_tweet_indices]
        if not available_indices:
            return "Yardım edin! Enkaz altındayım."
        selected_index = random.choice(available_indices)
        used_tweet_indices.add(selected_index)
        return self.tweets[selected_index]['text']

    def generate_agents(self, num_agents):
        agents = []
        for i in range(num_agents):
            node = random.choice(list(self.G.nodes(data=True)))
            role = random.choice(list(AgentRole))  # Başlangıçta rastgele rol ata
            agents.append(Agent(node[1]['x'], node[1]['y'], f"A{i+1}", role))
        return agents

    def calculate_utility(self, agent, patient):
        distance = math.sqrt((agent.x - patient.x)**2 + (agent.y - patient.y)**2)
        distance_factor = 1 / (1 + distance/1000)
        urgency_factor = patient.current_priority / 4
        waiting_factor = min(1, patient.waiting_time / 100)

        # Ajan rolüne göre önceliklendirme
        role_factor = 1
        if agent.role == AgentRole.SEARCH_RESCUE and patient.current_priority >= 3:
            role_factor = 1.5
        elif agent.role == AgentRole.MEDICAL and 2 <= patient.current_priority <= 3:
            role_factor = 1.3
        elif agent.role == AgentRole.FOOD_SUPPLY and patient.current_priority <= 2:
            role_factor = 1.2

        utility = (0.3 * distance_factor + 
                   0.3 * urgency_factor + 
                   0.2 * waiting_factor +
                   0.2 * role_factor)

        return utility, distance_factor, urgency_factor, waiting_factor, role_factor

    def assign_tasks(self):
        available_patients = [p for p in self.patients if p.status == PatientStatus.WAITING]
        idle_agents = [a for a in self.agents if a.status == AgentStatus.IDLE]

        if not available_patients or not idle_agents:
            logging.info("No available patients or idle agents.")
            return []

        assignments = []

        for agent in idle_agents:
            best_patient = None
            best_utility = -1
            best_factors = None

            for patient in available_patients:
                if agent.can_help(patient):
                    utility, distance_factor, urgency_factor, waiting_factor, role_factor = self.calculate_utility(agent, patient)
                    if utility > best_utility:
                        best_utility = utility
                        best_patient = patient
                        best_factors = (distance_factor, urgency_factor, waiting_factor, role_factor)

            if best_patient:
                assignments.append((agent, best_patient, best_utility, best_factors))
                available_patients.remove(best_patient)

        assignments.sort(key=lambda x: x[2], reverse=True)

        assigned_patients = []
        for agent, patient, utility, factors in assignments:
            agent.target = patient
            agent.status = AgentStatus.EN_ROUTE
            patient.assigned_agent = agent
            patient.status = PatientStatus.ASSIGNED
            assigned_patients.append(patient)
            travel_time = agent.calculate_travel_time(patient.x, patient.y)
            logging.info(f"Task assigned: Agent {agent.id} ({agent.role.name}) to Patient {patient.id} ({patient.patient_type.name}). " 
                         f"Utility: {utility:.2f}, "
                         f"Distance Factor: {factors[0]:.2f}, "
                         f"Urgency Factor: {factors[1]:.2f}, "
                         f"Waiting Factor: {factors[2]:.2f}, "
                         f"Role Factor: {factors[3]:.2f}, "
                         f"Estimated Travel Time: {travel_time:.2f} seconds")

        return assigned_patients

    def update_agent_status(self, agent_id, new_status):
        agent = next((a for a in self.agents if a.id == agent_id), None)
        if agent:
            if new_status == AgentStatus.ARRIVED:
                agent.status = AgentStatus.ARRIVED
                if agent.target:
                    agent.x, agent.y = agent.target.x, agent.target.y
                    agent.target.status = PatientStatus.BEING_TREATED
                    logging.info(f"Agent {agent.id} arrived at Patient {agent.target.id}. Treatment starting.")
            elif new_status == AgentStatus.TREATING:
                agent.status = AgentStatus.TREATING
                agent.treatment_start_time = self.current_time
                if agent.target:
                    agent.target.status = PatientStatus.BEING_TREATED
                logging.info(f"Agent {agent.id} is now treating Patient {agent.target.id}.")
            elif new_status == AgentStatus.COMPLETED:
                agent.status = AgentStatus.COMPLETED
                if agent.target:
                    agent.target.status = PatientStatus.TREATED
                    agent.target.last_help_time = self.current_time
                    logging.info(f"Agent {agent.id} completed treating Patient {agent.target.id}.")
                    agent.target.assigned_agent = None
                agent.target = None
                agent.status = AgentStatus.IDLE
            else:
                agent.status = new_status
            logging.info(f"Agent {agent.id} status updated to {new_status.name}")
        else:
            logging.warning(f"Agent {agent_id} not found")

    def change_agent_role(self, agent_id, new_role):
        agent = next((a for a in self.agents if a.id == agent_id), None)
        if agent:
            old_role = agent.role
            agent.role = new_role
            logging.info(f"Agent {agent.id} role changed from {old_role.name} to {new_role.name}")
            
            # Eğer ajan bir göreve atanmışsa ve yeni rolü bu görevi yapamıyorsa, görevi iptal et
            if agent.target and not agent.can_help(agent.target):
                patient = agent.target
                patient.interrupt_treatment()
                agent.target = None
                agent.status = AgentStatus.IDLE
                logging.info(f"Agent {agent.id}'s current task for Patient {patient.id} has been cancelled due to role change.")
            
            return True
        return False

    def get_agent_info(self, agent_id):
        agent = next((a for a in self.agents if a.id == agent_id), None)
        if agent:
            return f"Agent {agent.id}: Status - {agent.status.name}, " \
                   f"Role - {agent.role.name}, " \
                   f"Target - {agent.target.id if agent.target else 'None'}"
        return "Agent not found"

    def get_patient_info(self, patient_id):
        patient = next((p for p in self.patients if p.id == patient_id), None)
        if patient:
            status_info = {
                PatientStatus.WAITING: "Waiting for help",
                PatientStatus.ASSIGNED: "Help is on the way",
                PatientStatus.BEING_TREATED: "Currently being treated",
                PatientStatus.TREATED: "Treatment completed"
            }
            return f"Patient {patient.id}: Status - {status_info[patient.status]}, " \
                   f"Type - {patient.patient_type.name}, " \
                   f"Priority - {patient.current_priority}, " \
                   f"Assigned Agent - {patient.assigned_agent.id if patient.assigned_agent else 'None'}, " \
                   f"Treatment Progress - {patient.treatment_progress}%, " \
                   f"Tweet - {patient.tweet[:50]}..."
        return "Patient not found"

    def step(self):
        self.current_time += 1
        for patient in self.patients:
            patient.update(self.current_time)
        for agent in self.agents:
            agent.update(self.current_time)
        self.assign_tasks()

    def get_patient_annotation(self, patient):
        status_info = {
            PatientStatus.WAITING: "W",
            PatientStatus.ASSIGNED: "A",
            PatientStatus.BEING_TREATED: "T",
            PatientStatus.TREATED: "D"
        }
        return f"{patient.id}\n{status_info[patient.status]}"

    def get_patient_color(self, patient):
        if patient.status == PatientStatus.TREATED:
            return 'green'
        elif patient.status == PatientStatus.BEING_TREATED:
            return 'yellow'
        elif patient.status == PatientStatus.ASSIGNED:
            return 'orange'
        else:  # WAITING
            if patient.patient_type == PatientType.TRAPPED:
                return 'red'
            elif patient.patient_type == PatientType.INJURED:
                return 'purple'
            else:  # NEEDS_SUPPLY
                return 'blue'

    def get_agent_color(self, agent):
        if agent.status == AgentStatus.IDLE:
            base_color = 'lightgreen'
        elif agent.status == AgentStatus.EN_ROUTE:
            base_color = 'yellow'
        elif agent.status == AgentStatus.TREATING:
            base_color = 'red'
        else:  # ARRIVED or COMPLETED
            base_color = 'blue'

        if agent.role == AgentRole.SEARCH_RESCUE:
            return mcolors.to_rgba(base_color, alpha=1.0)
        elif agent.role == AgentRole.MEDICAL:
            return mcolors.to_rgba(base_color, alpha=0.7)
        else:  # FOOD_SUPPLY
            return mcolors.to_rgba(base_color, alpha=0.4)

class SimulationGUI(QMainWindow):
    def __init__(self, simulation):
        super().__init__()
        self.simulation = simulation
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Simulation Control')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        control_layout = QVBoxLayout()
        
        self.assign_button = QPushButton('Assign Tasks')
        self.assign_button.clicked.connect(self.assign_tasks)
        control_layout.addWidget(self.assign_button)

        self.step_button = QPushButton('Step Simulation')
        self.step_button.clicked.connect(self.step_simulation)
        control_layout.addWidget(self.step_button)

        self.agent_combo = QComboBox()
        self.update_agent_combo()
        control_layout.addWidget(self.agent_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(['En Route', 'Arrived', 'Treating', 'Completed'])
        control_layout.addWidget(self.status_combo)

        self.role_combo = QComboBox()
        self.role_combo.addItems([role.name for role in AgentRole])
        control_layout.addWidget(self.role_combo)

        self.update_status_button = QPushButton('Update Agent Status')
        self.update_status_button.clicked.connect(self.update_agent_status)
        control_layout.addWidget(self.update_status_button)

        self.change_role_button = QPushButton('Change Agent Role')
        self.change_role_button.clicked.connect(self.change_agent_role)
        control_layout.addWidget(self.change_role_button)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        control_layout.addWidget(self.info_text)

        main_layout.addLayout(control_layout)

        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        ox.plot_graph(self.simulation.G, ax=self.ax, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        self.patient_scatter = self.ax.scatter([], [], c=[], label='Patients')
        self.agent_scatter = self.ax.scatter([], [], c=[], marker='s', s=50, label='Agents')
        
        self.canvas = FigureCanvas(self.fig)
        main_layout.addWidget(self.canvas)

        central_widget.setLayout(main_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(1000)  # Update every 1000 ms

    def update_agent_combo(self):
        self.agent_combo.clear()
        for agent in self.simulation.agents:
            self.agent_combo.addItem(f"Agent {agent.id} ({agent.role.name})")

    def assign_tasks(self):
        assigned_patients = self.simulation.assign_tasks()
        self.info_text.append("Tasks assigned")
        for patient in assigned_patients:
            self.info_text.append(f"Patient {patient.id} assigned to Agent {patient.assigned_agent.id}")

    def step_simulation(self):
        self.simulation.step()
        self.info_text.append(f"Simulation stepped. Current time: {self.simulation.current_time} seconds")

    def update_agent_status(self):
        agent_id = self.agent_combo.currentText().split()[1]
        status_text = self.status_combo.currentText()
        status_map = {
            'En Route': AgentStatus.EN_ROUTE,
            'Arrived': AgentStatus.ARRIVED,
            'Treating': AgentStatus.TREATING,
            'Completed': AgentStatus.COMPLETED
        }
        self.simulation.update_agent_status(agent_id, status_map[status_text])
        self.info_text.append(f"Agent {agent_id} status updated to {status_text}")

    def change_agent_role(self):
        agent_id = self.agent_combo.currentText().split()[1]
        new_role = AgentRole[self.role_combo.currentText()]
        if self.simulation.change_agent_role(agent_id, new_role):
            self.info_text.append(f"Agent {agent_id} role changed to {new_role.name}")
            if any(a.id == agent_id and a.status != AgentStatus.IDLE for a in self.simulation.agents):
                self.info_text.append(f"Warning: Agent {agent_id}'s current task may have been cancelled due to role change.")
            self.update_agent_combo()
        else:
            self.info_text.append(f"Failed to change role for Agent {agent_id}")

    def update_plot(self):
        self.ax.clear()
        ox.plot_graph(self.simulation.G, ax=self.ax, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)

        patient_positions = [(p.x, p.y) for p in self.simulation.patients]
        patient_colors = [self.simulation.get_patient_color(p) for p in self.simulation.patients]
        self.ax.scatter(*zip(*patient_positions), c=patient_colors, label='Patients')

        # Hasta isimlerini ekleme
        for patient in self.simulation.patients:
            self.ax.annotate(patient.id, (patient.x, patient.y), xytext=(3, 3), 
                             textcoords='offset points', fontsize=8)

        agent_positions = [(a.x, a.y) for a in self.simulation.agents]
        agent_colors = [self.simulation.get_agent_color(a) for a in self.simulation.agents]
        self.ax.scatter(*zip(*agent_positions), c=agent_colors, marker='s', s=50, label='Agents')

        # Ajan isimlerini ekleme
        for agent in self.simulation.agents:
            self.ax.annotate(agent.id, (agent.x, agent.y), xytext=(3, 3), 
                             textcoords='offset points', fontsize=8)

        self.ax.legend()
        self.canvas.draw()

# Ana uygulama
if __name__ == "__main__":
    # Harita oluşturma
    center_point = (39.7467, 39.4917)  # Erzincan koordinatları
    G = ox.graph_from_point(center_point, dist=3000, network_type='drive')
    G = ox.project_graph(G)

    # Simülasyon başlatma
    tweets_file = 'tweets.json'  # Tweet dosyasının yolunu buraya girin
    sim = Simulation(G, num_patients=20, tweets_file=tweets_file, num_agents=5)

    app = QApplication(sys.argv)
    gui = SimulationGUI(sim)
    gui.show()
    sys.exit(app.exec_())