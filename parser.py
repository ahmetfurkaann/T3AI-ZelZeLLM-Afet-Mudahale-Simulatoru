import json
import requests
import random
from datetime import datetime
import re

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


gerekliler_json_data = [

    {"role": "system", "content": "Sen yardımcı bir asistansın. Görevin, sana verilen mesajda, eğer varsa ihtiyaç malzemelerinin bilgisini yazman. Varsa yaz, yoksa None yaz. Şu formatta yaz: Gerekliler: ..." },
    {"role": "user", "content": "Kahramanmaraş türkoğlu ilçesi şekeroba köyü çağrı sokak no 4 çadır yatak ısıtıcı ölen insanlae için de kefen ihtiyacı var  iletişim:05435379496"},
    {"role": "assistant", "content": "Gerekliler: Çadır, Yatak, Isıtıcı, Kefen "},

    {"role": "user", "content": "Kahramanmaraş Göksun Taşoluk köyü barınma ve erzak ihtiyaçları var lütfen paylasırmısınız teyitli numarasını atabilirim"},
    {"role": "assistant", "content": "Gerekliler: Barınma ve erzak ihtiyaçları"},

    {"role": "user", "content": "Narlıca mahallesi cumhuriyet caddesi 227.sokak no 12 aksan düğün salonu arkasındaki apartman tır garajı yanı bina no 12 Antakya  +90 (552) 404 66 88 türkan  Acil gıda ihtiyacı va"},
]

Konum_json_data = [

    {"role": "system", "content": "Sen yardımcı bir asistansın. Görevin, sana verilen mesajda, eğer varsa ihtiyaç duyulan konumun lokasyon bilgisini yazman. Varsa yaz, yoksa None yaz. Şu formatta yaz: Konum: ..." },
    {"role": "user", "content": "Kahramanmaraş türkoğlu ilçesi şekeroba köyü çağrı sokak no 4 çadır yatak ısıtıcı ölen insanlae için de kefen ihtiyacı var  iletişim:05435379496"},
    {"role": "assistant", "content": "Lokasyon: Kahramanmaraş"},

    {"role": "user", "content": "Gaziantep'de Göksun Taşoluk köyü barınma ve erzak ihtiyaçları var lütfen paylasırmısınız teyitli numarasını atabilirim"},
    {"role": "assistant", "content": "Lokasyon: Gaziantep'de"},

    {"role": "user", "content": "Narlıca mahallesi cumhuriyet caddesi 227.sokak no 12 aksan düğün salonu arkasındaki apartman tır garajı yanı bina no 12 Antakya  +90 (552) 404 66 88 türkan  Acil gıda ihtiyacı va"},
]


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


predict(iletisim_json_data)
predict(gerekliler_json_data)