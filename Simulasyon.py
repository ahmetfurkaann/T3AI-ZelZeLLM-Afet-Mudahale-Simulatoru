import matplotlib
matplotlib.use('TkAgg')

import random
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from enum import Enum
import matplotlib.colors as mcolors
from tqdm import tqdm
import osmnx as ox
import networkx as nx
import requests
import json
from pydantic import BaseModel
from typing import List
import logging
from datetime import datetime
import csv
import os
from matplotlib.patches import Rectangle, Patch
from scipy.optimize import linear_sum_assignment

# JSON verisi
chat_model_config = {
    "model": "/home/ubuntu/hackathon_model_2/",
    "temperature": 0.01,
    "top_p": 0.95,
    "max_tokens": 1024,
    "repetition_penalty": 1.1,
    "stop_token_ids": [
        128001,
        128009
    ],
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

class PriorityLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class StreetType(Enum):
    MAIN_ROAD = 1
    SIDE_STREET = 2

class StreetStatus(Enum):
    OPEN = 1
    PARTIALLY_BLOCKED = 2
    CLOSED = 3

class VictimStatus(Enum):
    TRAPPED = 1
    RESCUED = 2
    TREATED = 3
    STABILIZED = 4

class AgentRole(Enum):
    SEARCH_RESCUE = 1
    MEDICAL = 2
    FOOD_SUPPLY = 3

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

class Victim:
    def __init__(self, x, y, id, tweet, priority, G, region_id, region_difficulty, simulation):
        self.x = x
        self.y = y
        self.node = get_nearest_node(G, x, y)
        self.id = id
        self.tweet = tweet
        self.priority = priority
        self.status = VictimStatus.TRAPPED
        self.waiting_time = 0
        self.rescue_time = 0
        self.treatment_time = 0
        self.region_id = region_id
        self.region_difficulty = region_difficulty
        self.simulation = simulation
        self.initial_priority = priority
        self.time_in_current_priority = 0
        self.last_help_time = 0
        self.priority_counter = 0
        self.priority_threshold = self.get_priority_threshold()
        self.deterioration_rate = self.calculate_deterioration_rate()

    def get_priority_threshold(self):
        thresholds = {
            PriorityLevel.LOW: 100,
            PriorityLevel.MEDIUM: 150,
            PriorityLevel.HIGH: 200,
            PriorityLevel.CRITICAL: float('inf')  # CRITICAL seviyesi artmayacak
        }
        return thresholds[self.priority]

    def calculate_deterioration_rate(self):
        base_rate = 0.001
        return base_rate * self.region_difficulty * self.priority.value

    def update(self):
        if self.status == VictimStatus.TRAPPED:
            self.waiting_time += 1
            self.priority_counter += 1

            if random.random() < self.deterioration_rate:
                self.escalate_priority()

            if self.priority_counter >= self.priority_threshold:
                self.escalate_priority()
                self.priority_counter = 0
                self.priority_threshold = self.get_priority_threshold()
                self.deterioration_rate = self.calculate_deterioration_rate()

        elif self.status == VictimStatus.RESCUED:
            self.rescue_time += 1
            if self.rescue_time >= 20:  # 20 adımdan sonra tedavi edilmiş sayılsın
                self.status = VictimStatus.TREATED
                self.rescue_time = 0

        elif self.status == VictimStatus.TREATED:
            self.treatment_time += 1
            if self.treatment_time >= 30:  # 30 adımdan sonra stabilize edilmiş sayılsın
                self.status = VictimStatus.STABILIZED
                self.treatment_time = 0

    def escalate_priority(self):
        if self.priority.value < PriorityLevel.CRITICAL.value:
            self.priority = PriorityLevel(self.priority.value + 1)
            self.time_in_current_priority = 0
            print(f"Victim {self.id} priority escalated to {self.priority.name}")

    def deescalate_priority(self):
        if self.priority.value > self.initial_priority.value:
            self.priority = PriorityLevel(self.priority.value - 1)
            self.time_in_current_priority = 0
            print(f"Victim {self.id} priority de-escalated to {self.priority.name}")

class Agent:
    def __init__(self, node, role, capacity, id, G, use_resources):
        self.node = node
        self.x, self.y = G.nodes[node]['x'], G.nodes[node]['y']
        self.role = role
        self.capacity = capacity
        self.resources = capacity
        self.id = id
        self.stationary = False
        self.last_action = None
        self.specialized_priority = self.get_specialized_priority()
        self.use_resources = use_resources
        self.target_victim = None
        self.target_region = None
        self.last_target_update = 0

    def get_specialized_priority(self):
        if self.role == AgentRole.SEARCH_RESCUE:
            return [PriorityLevel.CRITICAL, PriorityLevel.HIGH]
        elif self.role == AgentRole.MEDICAL:
            return [PriorityLevel.HIGH, PriorityLevel.MEDIUM]
        elif self.role == AgentRole.FOOD_SUPPLY:
            return [PriorityLevel.MEDIUM, PriorityLevel.LOW]

    def move_to(self, target_node, G):
        if not self.stationary:
            self.node = target_node
            self.x, self.y = G.nodes[target_node]['x'], G.nodes[target_node]['y']
            self.last_action = f"Moved to {target_node}"

    def use_resource(self, amount):
        if self.use_resources:
            self.resources = max(0, self.resources - amount)

    def is_available(self):
        return (not self.use_resources) or (self.resources > 0 and not self.stationary)

    def can_help(self, victim):
        if self.role == AgentRole.SEARCH_RESCUE:
            return victim.status == VictimStatus.TRAPPED
        elif self.role == AgentRole.MEDICAL:
            return victim.status == VictimStatus.RESCUED
        elif self.role == AgentRole.FOOD_SUPPLY:
            return victim.status in [VictimStatus.TREATED, VictimStatus.STABILIZED]

    def refill_resources(self):
        if self.use_resources:
            self.resources = self.capacity
            self.last_action = "Refilled resources"

    def calculate_utility(self, victim, current_time):
        if self.role != AgentRole.SEARCH_RESCUE:
            return 0

        distance = math.sqrt((self.x - victim.x)**2 + (self.y - victim.y)**2)
        distance_factor = 1 / (1 + distance/1000)
        urgency_factor = victim.priority.value / PriorityLevel.CRITICAL.value
        waiting_time = current_time - victim.last_help_time
        waiting_factor = min(1, waiting_time / 100)
        difficulty_factor = victim.region_difficulty
        deterioration_factor = victim.deterioration_rate * 1000

        utility = (0.2 * distance_factor + 
                   0.3 * urgency_factor + 
                   0.2 * waiting_factor + 
                   0.15 * difficulty_factor +
                   0.15 * deterioration_factor)

        return utility

    def decide_region(self, region_stats, agent_distribution):
        if not region_stats:
            return None

        total_agents = sum(agent_distribution.values())
        
        region_scores = {}
        for region_id, stats in region_stats.items():
            victim_score = stats['victim_count'] * stats['avg_priority']
            difficulty_score = stats['difficulty']
            agent_ratio = agent_distribution.get(region_id, 0) / total_agents if total_agents > 0 else 0
            
            # Ajan oranı düşükse ve kurban sayısı yüksekse skoru artır
            score = victim_score * (1 + (1 - agent_ratio)) / difficulty_score
            region_scores[region_id] = score

        return max(region_scores, key=region_scores.get)

class Simulation:
    def __init__(self, G, num_agents, max_steps, tweets_file, use_resources):
        self.G = G
        self.max_steps = 2000  # 1000'den 2000'e çıkardık
        self.current_step = 0
        self.streets = self.generate_streets()
        self.create_regions(5)
        self.tweets = load_tweets(tweets_file)
        if not self.tweets:
            print("Tweet dosyası yüklenemedi. Varsayılan tweet'ler kullanılacak.")
            self.tweets = [{"text": f"Yardım edin! Enkaz altındayım. Konum: {i}"} for i in range(1000)]
        self.victims = []
        self.agents = self.generate_agents(num_agents, use_resources)
        self.num_agents = num_agents
        self.resource_stations = self.generate_resource_stations(3)
        self.setup_logging()
        self.report_data = []
        self.use_resources = use_resources
        self.communication_range = 500
        self.manual_victim_mode = False

    def generate_agents(self, num_agents, use_resources):
        agents = []
        nodes = list(self.G.nodes())
        roles = ([AgentRole.SEARCH_RESCUE] * int(num_agents * 0.5) +
                 [AgentRole.MEDICAL] * int(num_agents * 0.3) +
                 [AgentRole.FOOD_SUPPLY] * int(num_agents * 0.2))
        random.shuffle(roles)
        for i, role in enumerate(roles[:num_agents]):
            node = random.choice(nodes)
            capacity = random.randint(15, 25) if role == AgentRole.SEARCH_RESCUE else random.randint(10, 20)
            agents.append(Agent(node, role, capacity, f"A{i+1}", self.G, use_resources))
        return agents

    def setup_logging(self):
        self.logger = logging.getLogger('disaster_simulation')
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler('simulation.log')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log_step(self):
        status = self.get_detailed_status()
        
        self.logger.info(f"Step {self.current_step}: Trapped: {status['Trapped']}, "
                         f"Rescued: {status['Rescued']}, Treated: {status['Treated']}, "
                         f"Stabilized: {status['Stabilized']}, Success Rate: {status['Success Rate']:.2%}")
        
        for agent in self.agents:
            if agent.last_action:
                self.logger.info(f"Agent {agent.id} ({agent.role.name}): {agent.last_action}")
        
        self.report_data.append(status)

    def generate_report(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"simulation_report_{timestamp}.csv"
        
        fieldnames = ['Step', 'Total Victims', 'Trapped', 'Rescued', 'Treated', 'Stabilized', 'Success Rate']
        
        with open(filename, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for data in self.report_data:
                row = {
                    'Step': data['Step'],
                    'Total Victims': data['Total Victims'],
                    'Trapped': data['Trapped'],
                    'Rescued': data['Rescued'],
                    'Treated': data['Treated'],
                    'Stabilized': data['Stabilized'],
                    'Success Rate': data['Success Rate']
                }
                writer.writerow(row)
        
        self.logger.info(f"Report generated: {filename}")

    def generate_streets(self):
        streets = {}
        for u, v, data in self.G.edges(data=True):
            street_type = StreetType.MAIN_ROAD if data.get('highway') in ['motorway', 'trunk', 'primary', 'secondary'] else StreetType.SIDE_STREET
            street_status = StreetStatus.OPEN
            streets[(u, v)] = (street_type, street_status)
        return streets

    def create_regions(self, num_regions):
        x_min, y_min, x_max, y_max = (
            min(self.G.nodes[n]['x'] for n in self.G.nodes()),
            min(self.G.nodes[n]['y'] for n in self.G.nodes()),
            max(self.G.nodes[n]['x'] for n in self.G.nodes()),
            max(self.G.nodes[n]['y'] for n in self.G.nodes())
        )
        
        width = (x_max - x_min) / num_regions
        height = (y_max - y_min) / num_regions
        
        self.regions = {}
        for i in range(num_regions):
            for j in range(num_regions):
                region_id = i * num_regions + j
                self.regions[region_id] = {
                    'x_range': (x_min + i * width, x_min + (i + 1) * width),
                    'y_range': (y_min + j * height, y_min + (j + 1) * height),
                    'difficulty': random.uniform(1.0, 5.0)
                }

    def get_region(self, x, y):
        for region_id, region in self.regions.items():
            if (region['x_range'][0] <= x < region['x_range'][1] and
                region['y_range'][0] <= y < region['y_range'][1]):
                return region_id, region
        # Eğer bölge bulunamazsa, varsayılan bir bölge döndür
        return 0, {'difficulty': 1.0}

    def add_manual_victim(self, x, y, priority):
        region_id, region = self.get_region(x, y)
        tweet = self.get_random_tweet(set())
        new_victim = Victim(x, y, f"V{len(self.victims)+1}", tweet, priority, self.G, region_id, region['difficulty'], self)
        self.victims.append(new_victim)
        print(f"Yeni kurban eklendi: {new_victim.id} at ({x:.2f}, {y:.2f}) with priority {priority.name}")

    def generate_victims(self, num_victims):
        nodes = list(self.G.nodes())
        used_tweet_indices = set()
        for i in tqdm(range(num_victims), desc="Kurbanlar oluşturuluyor ve tweetler analiz ediliyor"):
            node = random.choice(nodes)
            x, y = self.G.nodes[node]['x'], self.G.nodes[node]['y']
            tweet = self.get_random_tweet(used_tweet_indices)
            priority = get_priority_from_tweet(tweet)
            region_id, region = self.get_region(x, y)
            self.victims.append(Victim(x, y, f"V{i+1}", tweet, priority, self.G, region_id, region['difficulty'], self))

    def get_random_tweet(self, used_tweet_indices):
        available_indices = [i for i in range(len(self.tweets)) if i not in used_tweet_indices]
        if not available_indices:
            return "Yardım edin! Enkaz altındayım."
        selected_index = random.choice(available_indices)
        used_tweet_indices.add(selected_index)
        return self.tweets[selected_index]['text']

    def generate_resource_stations(self, num_stations):
        nodes = list(self.G.nodes())
        return random.sample(nodes, num_stations)

    def find_path(self, start_node, end_node):
        try:
            return nx.shortest_path(self.G, start_node, end_node, weight='length')
        except nx.NetworkXNoPath:
            self.logger.warning(f"No path found between nodes {start_node} and {end_node}")
            return None

    def move_agent(self, agent, target_x, target_y):
        if not agent.stationary:
            target_node = get_nearest_node(self.G, target_x, target_y)
            path = self.find_path(agent.node, target_node)
            if path and len(path) > 1:
                agent.move_to(path[1], self.G)
            else:
                self.logger.warning(f"Agent {agent.id} couldn't move towards target ({target_x}, {target_y})")

    def prioritize_victims(self, victims, agent):
        if agent.role == AgentRole.SEARCH_RESCUE:
            return sorted(
                [v for v in victims if v.status == VictimStatus.TRAPPED],
                key=lambda v: agent.calculate_utility(v, self.current_step),
                reverse=True
            )
        elif agent.role == AgentRole.FOOD_SUPPLY:
            return [v for v in victims if v.status in [VictimStatus.RESCUED, VictimStatus.TREATED] and 
                    ((v.x - agent.x)**2 + (v.y - agent.y)**2)**0.5 < 200]
        else:  # MEDICAL
            return sorted(
                [v for v in victims if v.status == VictimStatus.RESCUED],
                key=lambda v: (
                    v.priority.value * 10 +
                    v.waiting_time -
                    (abs(v.x - agent.x) + abs(v.y - agent.y)) / 10
                ),
                reverse=True
            )

    def update_street_status(self):
        edge = random.choice(list(self.streets.keys()))
        current_type, current_status = self.streets[edge]
        
        if current_status == StreetStatus.CLOSED:
            self.streets[edge] = (current_type, StreetStatus.PARTIALLY_BLOCKED)
        elif current_status == StreetStatus.PARTIALLY_BLOCKED:
            self.streets[edge] = (current_type, random.choice([StreetStatus.OPEN, StreetStatus.CLOSED]))
        else:
            self.streets[edge] = (current_type, StreetStatus.PARTIALLY_BLOCKED)

    def help_victim(self, agent, victim):
        if agent.role == AgentRole.SEARCH_RESCUE:
            victim.status = VictimStatus.RESCUED
            victim.last_help_time = self.current_step
        elif agent.role == AgentRole.MEDICAL:
            victim.status = VictimStatus.TREATED
            victim.priority = PriorityLevel.LOW
            victim.last_help_time = self.current_step
        elif agent.role == AgentRole.FOOD_SUPPLY:
            if victim.status == VictimStatus.RESCUED:
                victim.status = VictimStatus.TREATED
            victim.priority = PriorityLevel.LOW
            victim.last_help_time = self.current_step
        
        agent.use_resource(victim.priority.value)
        agent.last_action = f"Helped victim {victim.id} with priority {victim.priority.name}"

    def agents_can_communicate(self, agent1, agent2):
        distance = ((agent1.x - agent2.x)**2 + (agent1.y - agent2.y)**2)**0.5
        return distance <= self.communication_range

    def evaluate_regions(self):
        region_stats = {}
        for region_id in self.regions:
            victims_in_region = [v for v in self.victims if v.region_id == region_id and v.status == VictimStatus.TRAPPED]
            if victims_in_region:
                avg_priority = sum(v.priority.value for v in victims_in_region) / len(victims_in_region)
                region_stats[region_id] = {
                    'victim_count': len(victims_in_region),
                    'avg_priority': avg_priority,
                    'difficulty': self.regions[region_id]['difficulty']
                }
        return region_stats

    def find_nearest_helpable_victim(self, agent):
        helpable_victims = [v for v in self.victims if agent.can_help(v)]
        if helpable_victims:
            return min(helpable_victims, key=lambda v: ((agent.x - v.x)**2 + (agent.y - v.y)**2)**0.5)
        return None

    def step(self):
        if self.current_step >= self.max_steps or self.all_victims_saved():
            self.generate_report()
            return False

        self.update_street_status()

        for victim in self.victims:
            victim.update()

        for agent in self.agents:
            if agent.target_victim is None or not agent.can_help(agent.target_victim):
                nearest_helpable_victim = self.find_nearest_helpable_victim(agent)
                if nearest_helpable_victim:
                    agent.target_victim = nearest_helpable_victim
        
            if agent.target_victim:
                if agent.node == agent.target_victim.node:
                    self.help_victim(agent, agent.target_victim)
                    agent.target_victim = None
                else:
                    self.move_agent(agent, agent.target_victim.x, agent.target_victim.y)

        self.log_step()
        self.current_step += 1
        return True

    def all_victims_saved(self):
        return all(v.status == VictimStatus.STABILIZED for v in self.victims)

    def get_success_rate(self):
        total_victims = len(self.victims)
        if total_victims == 0:
            return 0

        rescued_weight = 0.3
        treated_weight = 0.6
        stabilized_weight = 1.0

        rescued_count = sum(1 for v in self.victims if v.status == VictimStatus.RESCUED)
        treated_count = sum(1 for v in self.victims if v.status == VictimStatus.TREATED)
        stabilized_count = sum(1 for v in self.victims if v.status == VictimStatus.STABILIZED)

        weighted_sum = (
            rescued_count * rescued_weight +
            treated_count * treated_weight +
            stabilized_count * stabilized_weight
        )

        return weighted_sum / total_victims

    def get_detailed_status(self):
        total_victims = len(self.victims)
        trapped = sum(1 for v in self.victims if v.status == VictimStatus.TRAPPED)
        rescued = sum(1 for v in self.victims if v.status == VictimStatus.RESCUED)
        treated = sum(1 for v in self.victims if v.status == VictimStatus.TREATED)
        stabilized = sum(1 for v in self.victims if v.status == VictimStatus.STABILIZED)

        return {
            "Step": self.current_step,
            "Total Victims": total_victims,
            "Trapped": trapped,
            "Rescued": rescued,
            "Treated": treated,
            "Stabilized": stabilized,
            "Success Rate": self.get_success_rate()
        }

    def setup_risk_areas(self):
        risk_area_choice = input("Risk alanlarını nasıl belirlemek istersiniz? (M: Manuel, A: Otomatik): ").lower()
        
        if risk_area_choice == 'm':
            self.select_risk_areas()
        elif risk_area_choice == 'a':
            num_areas = int(input("Kaç adet otomatik risk alanı oluşturulsun? "))
            self.create_automatic_risk_areas(num_areas)
        else:
            print("Geçersiz seçim. Otomatik risk alanları oluşturuluyor.")
            self.create_automatic_risk_areas()

    def select_risk_areas(self):
        fig, ax = ox.plot_graph(self.G, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        risk_areas = []

        # Haritanın boyutlarını al
        x_min, y_min, x_max, y_max = ax.get_xlim()[0], ax.get_ylim()[0], ax.get_xlim()[1], ax.get_ylim()[1]
        map_width = x_max - x_min
        map_height = y_max - y_min

        def on_click(event):
            if event.button == 1:  # Sol tıklama
                x, y = event.xdata, event.ydata
                width, height = map_width * 0.05, map_height * 0.05  # Haritanın %5'i kadar
                rect = Rectangle((x-width/2, y-height/2), width, height, fill=False, edgecolor='red')
                ax.add_patch(rect)
                risk_areas.append((x, y, width, height))
                plt.draw()
            elif event.button == 3:  # Sağ tıklama
                plt.close()

        fig.canvas.mpl_connect('button_press_event', on_click)
        plt.title("Sol tık: Risk alanı ekle, Sağ tık: Bitir")
        plt.show()

        # Risk alanlarını bölgelere uygula
        for x, y, width, height in risk_areas:
            for region_id, region in self.regions.items():
                # Risk alanı ve bölgenin kesişim alanını hesapla
                intersection_x_min = max(region['x_range'][0], x - width/2)
                intersection_x_max = min(region['x_range'][1], x + width/2)
                intersection_y_min = max(region['y_range'][0], y - height/2)
                intersection_y_max = min(region['y_range'][1], y + height/2)

                # Kesişim varsa, kesişim alanının oranına göre zorluk seviyesini artır
                if intersection_x_min < intersection_x_max and intersection_y_min < intersection_y_max:
                    intersection_area = (intersection_x_max - intersection_x_min) * (intersection_y_max - intersection_y_min)
                    region_area = (region['x_range'][1] - region['x_range'][0]) * (region['y_range'][1] - region['y_range'][0])
                    impact_ratio = intersection_area / region_area
                    region['difficulty'] = min(2.0, region['difficulty'] + impact_ratio)

        print(f"{len(risk_areas)} risk alanı manuel olarak eklendi.")

    def create_automatic_risk_areas(self, num_areas=3):
        for _ in range(num_areas):
            region_id = random.choice(list(self.regions.keys()))
            self.regions[region_id]['difficulty'] = 2.0  # Maksimum zorluk seviyesi
        print(f"{num_areas} risk alanı otomatik olarak eklendi.")

    def manually_place_victims(self):
        fig, ax = ox.plot_graph(self.G, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        
        def on_click(event):
            if event.button == 1:  # Sol tıklama
                x, y = event.xdata, event.ydata
                priority = PriorityLevel(int(input("Afetzede önceliğini girin (1: Düşük, 2: Orta, 3: Yüksek, 4: Kritik): ")))
                self.add_manual_victim(x, y, priority)
                ax.scatter(x, y, c=get_color_for_victim(self.victims[-1]), zorder=2)
                ax.text(x, y, self.victims[-1].id, fontsize=8)
                plt.draw()
            elif event.button == 3:  # Sağ tıklama
                plt.close()

        fig.canvas.mpl_connect('button_press_event', on_click)
        plt.title("Sol tık: Afetzede ekle, Sağ tık: Bitir")
        plt.show()

    def calculate_optimal_agent_placement(self):
        # Ajan sayılarını belirle
        num_search_rescue = sum(1 for agent in self.agents if agent.role == AgentRole.SEARCH_RESCUE)
        num_medical = sum(1 for agent in self.agents if agent.role == AgentRole.MEDICAL)
        num_food_supply = sum(1 for agent in self.agents if agent.role == AgentRole.FOOD_SUPPLY)

        # Afetzede yoğunluğunu hesapla
        victim_density = np.zeros((len(self.regions), 4))  # 4 öncelik seviyesi için
        for victim in self.victims:
            victim_density[victim.region_id][victim.priority.value - 1] += 1

        # Ajan yerleşim matrisi oluştur
        placement_matrix = np.zeros((len(self.regions), 3))  # 3 ajan tipi için

        # Öncelikle arama kurtarma ajanlarını yerleştir
        search_rescue_score = victim_density[:, 2] * 2 + victim_density[:, 3] * 3  # Yüksek ve kritik öncelikli afetzedelere ağırlık ver
        top_regions = np.argsort(search_rescue_score)[::-1][:num_search_rescue]
        placement_matrix[top_regions, 0] = 1

        # Medikal ajanları yerleştir
        medical_score = victim_density[:, 1] * 2 + victim_density[:, 2] * 3  # Orta ve yüksek öncelikli afetzedelere ağırlık ver
        available_regions = np.where(placement_matrix[:, 0] == 0)[0]
        top_medical_regions = available_regions[np.argsort(medical_score[available_regions])[::-1][:num_medical]]
        placement_matrix[top_medical_regions, 1] = 1

        # Gıda tedarik ajanlarını yerleştir
        food_score = victim_density[:, 0] * 2 + victim_density[:, 1]  # Düşük ve orta öncelikli afetzedelere ağırlık ver
        available_regions = np.where(np.sum(placement_matrix, axis=1) == 0)[0]
        top_food_regions = available_regions[np.argsort(food_score[available_regions])[::-1][:num_food_supply]]
        placement_matrix[top_food_regions, 2] = 1

        return placement_matrix

    def apply_optimal_agent_placement(self, placement_matrix):
        agent_index = {AgentRole.SEARCH_RESCUE: 0, AgentRole.MEDICAL: 0, AgentRole.FOOD_SUPPLY: 0}
        
        for region_id, placements in enumerate(placement_matrix):
            for role_index, count in enumerate(placements):
                if count > 0:
                    role = list(AgentRole)[role_index]
                    agent = next((agent for agent in self.agents if agent.role == role and not hasattr(agent, 'placed')), None)
                    if agent:
                        region_center_x = (self.regions[region_id]['x_range'][0] + self.regions[region_id]['x_range'][1]) / 2
                        region_center_y = (self.regions[region_id]['y_range'][0] + self.regions[region_id]['y_range'][1]) / 2
                        agent.node = get_nearest_node(self.G, region_center_x, region_center_y)
                        agent.x, agent.y = self.G.nodes[agent.node]['x'], self.G.nodes[agent.node]['y']
                        agent.placed = True
                        agent_index[role] += 1
                    else:
                        print(f"Uyarı: {role.name} rolü için yeterli ajan yok. Bölge {region_id}'ye yerleştirilemedi.")

        # Yerleştirilmemiş ajanları rastgele bölgelere yerleştir
        unplaced_agents = [agent for agent in self.agents if not hasattr(agent, 'placed')]
        for agent in unplaced_agents:
            random_region_id = random.choice(list(self.regions.keys()))
            region_center_x = (self.regions[random_region_id]['x_range'][0] + self.regions[random_region_id]['x_range'][1]) / 2
            region_center_y = (self.regions[random_region_id]['y_range'][0] + self.regions[random_region_id]['y_range'][1]) / 2
            agent.node = get_nearest_node(self.G, region_center_x, region_center_y)
            agent.x, agent.y = self.G.nodes[agent.node]['x'], self.G.nodes[agent.node]['y']
            print(f"Uyarı: {agent.id} ({agent.role.name}) rastgele bölge {random_region_id}'ye yerleştirildi.")

        # 'placed' özelliğini temizle
        for agent in self.agents:
            if hasattr(agent, 'placed'):
                delattr(agent, 'placed')

        print("Ajan yerleşimi tamamlandı.")

    def optimize_agent_placement(self):
        self.manually_place_victims()
        optimal_placement = self.calculate_optimal_agent_placement()
        
        # Optimal yerleşimi görselleştir
        fig, ax = ox.plot_graph(self.G, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        for region_id, placements in enumerate(optimal_placement):
            region_center_x = (self.regions[region_id]['x_range'][0] + self.regions[region_id]['x_range'][1]) / 2
            region_center_y = (self.regions[region_id]['y_range'][0] + self.regions[region_id]['y_range'][1]) / 2
            for role_index, count in enumerate(placements):
                if count > 0:
                    color = ['blue', 'red', 'green'][role_index]
                    ax.scatter(region_center_x, region_center_y, c=color, marker='s', s=50, zorder=3)
        
        for victim in self.victims:
            ax.scatter(victim.x, victim.y, c=get_color_for_victim(victim), zorder=2)
        
        plt.title("Optimal Ajan Yerleşimi")
        plt.show()

        apply_placement = input("Bu optimal yerleşimi uygulamak istiyor musunuz? (E/H): ").lower() == 'e'
        if apply_placement:
            self.apply_optimal_agent_placement(optimal_placement)
            print("Optimal ajan yerleşimi uygulandı.")
        else:
            print("Optimal yerleşim uygulanmadı. Mevcut ajan konumları korundu.")

def get_color_for_victim(victim):
    if victim.status == VictimStatus.TRAPPED:
        return {PriorityLevel.LOW: 'yellow', PriorityLevel.MEDIUM: 'orange',
                PriorityLevel.HIGH: 'red', PriorityLevel.CRITICAL: 'purple'}[victim.priority]
    elif victim.status == VictimStatus.RESCUED:
        return 'lightgreen'
    elif victim.status == VictimStatus.TREATED:
        return 'green'
    else:  # STABILIZED
        return 'darkgreen'

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
            return PriorityLevel(max(1, min(4, priority)))
        else:
            print(f"API çağrısı başarısız oldu. Hata kodu: {response.status_code}")
            return PriorityLevel(random.randint(1, 4))
    
    except Exception as e:
        print(f"API çağrısı sırasında bir hata oluştu: {e}")
        return PriorityLevel(random.randint(1, 4))

def ensure_graph_connectivity(G):
    if not nx.is_strongly_connected(G):
        largest_scc = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest_scc).copy()
    return G

# Main execution
if __name__ == "__main__":
    try:
        center_point = (39.7467, 39.4917)
        G = ox.graph_from_point(center_point, dist=3000, network_type='drive')
        G = ox.project_graph(G)
        G = ox.consolidate_intersections(G, rebuild_graph=True, tolerance=15, dead_ends=False)
        G = ensure_graph_connectivity(G)

        street_types = {}
        for u, v, data in G.edges(data=True):
            if 'highway' in data:
                if data['highway'] in ['motorway', 'trunk', 'primary', 'secondary']:
                    street_types[(u, v)] = StreetType.MAIN_ROAD
                else:
                    street_types[(u, v)] = StreetType.SIDE_STREET

        tweets_file = r'D:\zelzellm\tweets.json'  # Tweet JSON dosyanızın yolunu buraya ekleyin

        # Kullanıcıya kaynak kullanımı hakkında sor
        use_resources = input("Kaynakların tükenmesini simülasyona dahil etmek istiyor musunuz? (E/H): ").lower() == 'e'

        # Kullanıcıdan ajan sayısını al
        num_agents = int(input("Simülasyonda kaç ajan olsun? (Önerilen: 50) "))

        sim = Simulation(G, num_agents=num_agents, max_steps=2000, tweets_file=tweets_file, use_resources=use_resources)

        # Risk alanlarını ayarla
        sim.setup_risk_areas()

        # Optimize agent placement
        sim.optimize_agent_placement()

        # İki ayrı figür oluştur
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))

        # İlk harita (risk bölgeleri ile)
        ox.plot_graph(G, ax=ax1, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        scatter_victims1 = ax1.scatter([], [], c=[], zorder=2)
        scatter_agents1 = ax1.scatter([], [], c=[], marker='s', s=50, zorder=3)
        texts1 = [ax1.text(0, 0, '', fontsize=8) for _ in range(len(sim.victims) + len(sim.agents))]

        # Risk bölgelerini çiz (saydamlığı artırılmış)
        for region_id, region in sim.regions.items():
            color = plt.cm.RdYlGn(1 - (region['difficulty'] - 0.5) / 1.5)
            ax1.add_patch(plt.Rectangle((region['x_range'][0], region['y_range'][0]), 
                                        region['x_range'][1] - region['x_range'][0], 
                                        region['y_range'][1] - region['y_range'][0], 
                                        fill=True, alpha=0.2, color=color))

        ax1.set_title("Harita 1: Risk Bölgeleri ile")

        # İkinci harita (risk bölgeleri olmadan)
        ox.plot_graph(G, ax=ax2, node_size=0, edge_color='#999999', edge_linewidth=0.5, show=False)
        scatter_victims2 = ax2.scatter([], [], c=[], zorder=2)
        scatter_agents2 = ax2.scatter([], [], c=[], marker='s', s=50, zorder=3)
        texts2 = [ax2.text(0, 0, '', fontsize=8) for _ in range(len(sim.victims) + len(sim.agents))]

        ax2.set_title("Harita 2: Risk Bölgeleri olmadan")

        # Renk skalası gösterimi
        legend_elements = [
            Patch(facecolor='yellow', edgecolor='black', label='Düşük Öncelik'),
            Patch(facecolor='orange', edgecolor='black', label='Orta Öncelik'),
            Patch(facecolor='red', edgecolor='black', label='Yüksek Öncelik'),
            Patch(facecolor='purple', edgecolor='black', label='Kritik Öncelik'),
            Patch(facecolor='lightgreen', edgecolor='black', label='Kurtarılmış'),
            Patch(facecolor='green', edgecolor='black', label='Tedavi Edilmiş'),
            Patch(facecolor='darkgreen', edgecolor='black', label='Stabilize Edilmiş'),
            Patch(facecolor='blue', edgecolor='black', label='Arama Kurtarma Ajanı'),
            Patch(facecolor='red', edgecolor='black', label='Tıbbi Ajan'),
            Patch(facecolor='green', edgecolor='black', label='Gıda Tedarik Ajanı')
        ]

        fig.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5))

        def update(frame):
            if frame >= sim.max_steps or not sim.step():
                plt.close()
                return

            victim_colors = [get_color_for_victim(v) for v in sim.victims]
            victim_positions = [(v.x, v.y) for v in sim.victims]
            agent_positions = [(a.x, a.y) for a in sim.agents]
            agent_colors = ['blue' if a.role == AgentRole.SEARCH_RESCUE else 'red' if a.role == AgentRole.MEDICAL else 'green' for a in sim.agents]

            # İlk haritayı güncelle
            scatter_victims1.set_offsets(victim_positions)
            scatter_victims1.set_color(victim_colors)
            scatter_agents1.set_offsets(agent_positions)
            scatter_agents1.set_color(agent_colors)

            # İkinci haritayı güncelle
            scatter_victims2.set_offsets(victim_positions)
            scatter_victims2.set_color(victim_colors)
            scatter_agents2.set_offsets(agent_positions)
            scatter_agents2.set_color(agent_colors)

            for i, (victim, text1, text2) in enumerate(zip(sim.victims, texts1[:len(sim.victims)], texts2[:len(sim.victims)])):
                text1.set_position((victim.x, victim.y))
                text1.set_text(victim.id)
                text2.set_position((victim.x, victim.y))
                text2.set_text(victim.id)

            for i, (agent, text1, text2) in enumerate(zip(sim.agents, texts1[len(sim.victims):], texts2[len(sim.victims):])):
                text1.set_position((agent.x, agent.y))
                text1.set_text(agent.id)
                text2.set_position((agent.x, agent.y))
                text2.set_text(agent.id)

            status = sim.get_detailed_status()
            status_text = f"Step: {sim.current_step}\n"
            status_text += f"Trapped: {status['Trapped']}, Rescued: {status['Rescued']}, "
            status_text += f"Treated: {status['Treated']}, Stabilized: {status['Stabilized']}\n"
            status_text += f"Success Rate: {status['Success Rate']:.2%}"
            
            fig.suptitle(status_text)

        anim = FuncAnimation(fig, update, frames=sim.max_steps, interval=200, repeat=False)

        plt.show(block=True)

        # Simülasyon tamamlandıktan sonra raporu oluştur
        sim.generate_report()

    except Exception as e:
        print(f"Bir hata oluştu: {e}")
        import traceback
        traceback.print_exc()
