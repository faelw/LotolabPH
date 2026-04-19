import requests
from bs4 import BeautifulSoup
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
import sys

URL = "https://www.pcso.gov.ph/searchlottoresult.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": URL
}

def clean_numbers(number_string):
    return [int(n) for n in re.findall(r'\d+', number_string)]

def parse_date(date_string):
    try:
        dt = datetime.strptime(date_string.strip(), "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return date_string.strip()

def scrape_pcso_advanced():
    session = requests.Session()
    
    print("Passo 1: Acessando a página para capturar estrutura dinâmica...")
    try:
        res_inicial = session.get(URL, headers=HEADERS, timeout=15)
        soup_inicial = BeautifulSoup(res_inicial.text, 'html.parser')
        
        # Coleta dinamicamente TODOS os inputs ocultos (ViewStates de segurança do ASP.NET)
        payload = {}
        for input_tag in soup_inicial.find_all('input'):
            name = input_tag.get('name')
            if name:
                payload[name] = input_tag.get('value', '')
                
    except Exception as e:
        print(f"Erro ao capturar página inicial: {e}")
        sys.exit(1) # Força o erro para o GitHub Actions identificar a falha

    print("Passo 2: Montando o payload de busca inteligente...")
    hoje = datetime.now()
    mes_passado = hoje - timedelta(days=30)
    
    # Encontra os nomes exatos das caixas de seleção usando Regex para ignorar prefixos surpresa
    start_month = soup_inicial.find('select', id=re.compile(r'ddlStartMonth'))
    start_day = soup_inicial.find('select', id=re.compile(r'ddlStartDate'))
    start_year = soup_inicial.find('select', id=re.compile(r'ddlStartYear'))
    
    end_month = soup_inicial.find('select', id=re.compile(r'ddlEndMonth'))
    end_day = soup_inicial.find('select', id=re.compile(r'ddlEndDate'))
    end_year = soup_inicial.find('select', id=re.compile(r'ddlEndYear'))
    
    btn_search = soup_inicial.find('input', id=re.compile(r'btnSearch'))

    # Preenche o formulário com os valores reais baseados nos nomes dinâmicos encontrados
    if start_month: payload[start_month['name']] = mes_passado.strftime('%B')
    if start_day: payload[start_day['name']] = str(mes_passado.day).lstrip('0')
    if start_year: payload[start_year['name']] = mes_passado.strftime('%Y')

    if end_month: payload[end_month['name']] = hoje.strftime('%B')
    if end_day: payload[end_day['name']] = str(hoje.day).lstrip('0')
    if end_year: payload[end_year['name']] = hoje.strftime('%Y')
    
    if btn_search: payload[btn_search['name']] = 'Search Lotto'

    print("Passo 3: Submetendo a requisição de busca...")
    try:
        res_post = session.post(URL, data=payload, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res_post.text, 'html.parser')
        
        table = soup.find('table')
        if not table:
            print("ERRO CRÍTICO: Tabela não encontrada. A estrutura do site foi alterada drasticamente.")
            sys.exit(1)

        rows = table.find_all('tr')[1:] 
        jogos_dict = defaultdict(list)

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                nome_jogo = cols[0].text.strip()
                combinacao_str = cols[1].text.strip()
                data_str = parse_date(cols[2].text.strip())
                jackpot = cols[3].text.strip()
                vencedores = cols[4].text.strip()

                matriz_numeros = clean_numbers(combinacao_str)
                
                if matriz_numeros:
                    jogos_dict[nome_jogo].append({
                        "date": data_str,
                        "combination_str": combinacao_str,
                        "combination_array": matriz_numeros,
                        "jackpot": jackpot,
                        "winners": vencedores
                    })

        if not jogos_dict:
             print("ERRO: A tabela foi encontrada, mas estava vazia.")
             sys.exit(1)

        print("Passo 4: Estruturando e Salvando o JSON...")
        json_final = {
            "metadata": {
                "last_updated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "PCSO Official"
            },
            "ui_results": {},
            "analysis_data": {}
        }

        for jogo, resultados in jogos_dict.items():
            resultados.sort(key=lambda x: x['date'], reverse=True)
            top_10 = resultados[:10]

            json_final["ui_results"][jogo] = [
                {"date": r["date"], "numbers": r["combination_str"], "jackpot": r["jackpot"], "winners": r["winners"]}
                for r in top_10
            ]
            json_final["analysis_data"][jogo] = [r["combination_array"] for r in top_10]

        with open('pcso_master_data.json', 'w', encoding='utf-8') as f:
            json.dump(json_final, f, ensure_ascii=False, indent=4)
            
        print(f"Sucesso absoluto! JSON gerado com {len(jogos_dict.keys())} loterias diferentes.")

    except Exception as e:
        print(f"Erro fatal durante o processamento: {e}")
        sys.exit(1)

if __name__ == "__main__":
    scrape_pcso_advanced()
