import json
import requests
import random
from datetime import datetime
import re

url = "https://inference2.t3ai.org/v1/completions"


emergency_codes = """
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
"2 ÇOCUK ENKAZ ALTINDA!! Acil yardım gerekiyor."
"""

aciliyet_json_data = [
    {"role": "system", "content": "Sen yardımcı bir asistansın. Görevin, sana verilen mesajları şu şablona uygun şekilde aciliyet sırasına koymak. Şablon:" + emergency_codes },
    {"role": "user", "content": "Kahramanmaraş türkoğlu ilçesi şekeroba köyü çağrı sokak no 4 çadır yatak ısıtıcı ölen insanlae için de kefen ihtiyacı var  iletişim:05435379496"},
    {"role": "assistant", "content": "Aciliyet seviyesi: 1, "},
    {"role": "user", "content": "Yemek barınma ihtiyacı vardır lütfen RT yapalım  Orduzu leylekpinari mahallesi çıkmaz sokak veysel Karani camisi yanı / Malatya"},
]

talep_ozet_json_data = [

    {"role": "system", "content": "Sen yardımcı bir asistansın. Görevin, sana verilen deprem tweet'lerini özetlemek. Sadece özet çıkar." },
    {"role": "user", "content": "Kahramanmaraş türkoğlu ilçesi şekeroba köyü çağrı sokak no 4 çadır yatak ısıtıcı ölen insanlae için de kefen ihtiyacı var  iletişim:05435379496"},
    {"role": "assistant", "content": "Talep özeti: Kahramanmaraş türkoğlu ilçesi'ne çadır, yatak, ısıtıcı ve kefen gerek"},
    {"role": "user", "content": "Narlıca mahallesi cumhuriyet caddesi 227.sokak no 12 aksan düğün salonu arkasındaki apartman tır garajı yanı bina no 12 Antakya  +90 (552) 404 66 88 türkan  Acil gıda ihtiyacı va"},
]

iletisim_json_data = [

    {"role": "system", "content": "Sen yardımcı bir asistansın. Görevin, sana verilen mesajda, eğer varsa iletişim bilgisini yazman. Varsa yaz, yoksa None yaz. Şu formatta yaz: İletişim: ..." },
    {"role": "user", "content": "Kahramanmaraş türkoğlu ilçesi şekeroba köyü çağrı sokak no 4 çadır yatak ısıtıcı ölen insanlae için de kefen ihtiyacı var  iletişim:05435379496"},
    {"role": "assistant", "content": "İletişim: 05435379496"},

    {"role": "user", "content": "Kahramanmaraş Göksun Taşoluk köyü barınma ve erzak ihtiyaçları var lütfen paylasırmısınız teyitli numarasını atabilirim"},
    {"role": "assistant", "content": "İletişim: None"},

    {"role": "user", "content": "Narlıca mahallesi cumhuriyet caddesi 227.sokak no 12 aksan düğün salonu arkasındaki apartman tır garajı yanı bina no 12 Antakya  +90 (552) 404 66 88 türkan  Acil gıda ihtiyacı va"},
]

import json
import requests
import random
from datetime import datetime
import re

def Emergency_Level(text):
    match = re.search(r'Aciliyet Seviyesi:\s*(\d+)', text)
    
    if match:
        aciliyet_seviyesi = match.group(1)
        return "Aciliyet Seviyesi: "+ str(aciliyet_seviyesi)
    else:
        return "Aciliyet seviyesi bulunamadı."


def convert_to_special_format(json_data):
    output = "<|begin_of_text|>"
    for entry in json_data:
        if entry["role"] == "system":
            output += f'<|start_header_id|>system<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'
        elif entry["role"] == "user":
            output += f'\n<|start_header_id|>{entry["role"]}<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'
        elif entry["role"] == "assistant":
            output += f'\n<|start_header_id|>{entry["role"]}<|end_header_id|>\n\n{entry["content"]}<|eot_id|>'
    output += "\n<|start_header_id|>assistant<|end_header_id|>"
    return output

def predict(json_data):
    special_format_output = convert_to_special_format(json_data)
    
    payload = json.dumps({
      "model": "/home/ubuntu/hackathon_model_2/",
      "prompt": special_format_output,
      "temperature": 0.1,
      "top_p": 0.9,
      "max_tokens": 1024,
      "repetition_penalty": 1.1,
      "stop_token_ids": [
        128001,
        128009
      ],
      "skip_special_tokens": True
    })
    
    headers = {
      'Content-Type': 'application/json',
    }
    
    response = requests.post(url, headers=headers, data=payload)
    pretty_response = json.loads(response.text)
    
    return pretty_response['choices'][0]['text']

# Verilen tarihe göre interaction_id oluştur
def create_interaction_id():
    now = datetime.now()
    return now.strftime("%d%m%H%M%S")

# Rastgele user_id oluştur
def create_user_id():
    return random.randint(100000, 999999)

# ISO 8601 formatında timestamp oluştur
def create_timestamp():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# Geri bildirim JSON çıktısı oluşturma
def create_feedback_json(iletisim_json_data, talep_ozet_json_data):
    interaction_id = create_interaction_id()
    user_id = create_user_id()
    timestamp = create_timestamp()
    input_prompt = iletisim_json_data[1]["content"]
    
    model_response = predict(aciliyet_json_data)
    model_response = Emergency_Level(model_response)

    talep_ozet = predict(talep_ozet_json_data)
    iletisim = predict(iletisim_json_data)

    feedback_json = {
        "interaction_id": interaction_id,
        "user_id": user_id,
        "timestamp": timestamp,
        "content_generated": {
            "input_prompt": input_prompt,
            "response": model_response
        },
        "user_feedback": {
            "rating": "tweet_aciliyet_label_true",  # False & True
            "Talep_ozet": talep_ozet,
            "Iletisim": iletisim
        },
        "feedback_metadata": {
            "device": "mobile",  # Örnek: mobil cihaz
            "location": "Turkey",  # İsteğe bağlı
            "session_duration": 120  # Örnek: 120 saniye
        }
    }
    
    return feedback_json

# Geri bildirim JSON'u oluştur ve yazdır
feedback_json = create_feedback_json(iletisim_json_data, talep_ozet_json_data)
print(json.dumps(feedback_json, indent=2, ensure_ascii=False))


def feedback(rating_response)
    if not rating_response:
        hata_req = feedback_json['content_generated']['input_prompt']
        hata_res = feedback_json['content_generated']['response']
        #rating_response = feedback_json['user_feedback']['rating']
        
        iletisim_json_data.append({"role": "user", "content": hata_req + "Bu girdi," + hata_res + "Olarak yorumlandı fakat" + rating_response + "olmalıydı. bu hatayı tolere ederek cevapla"})
    
    
    feedback_json = create_feedback_json(iletisim_json_data, talep_ozet_json_data)
    print(json.dumps(feedback_json, indent=2, ensure_ascii=False))


rating_response = feedback_json['user_feedback']['rating']
feedback(rating_response)