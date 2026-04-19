import requests
from bs4 import BeautifulSoup
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta

# URL de busca da PCSO
URL = "https://www.pcso.gov.ph/searchlottoresult.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": URL
}

def clean_numbers(number_string):
    """
    Extrai apenas os números reais da string, ignorando traços ou espaços extras.
    Exemplo: "12-45-03-22" -> [12, 45, 3, 22]
    """
    return [int(n) for n in re.findall(r'\d+', number_string)]

def parse_date(date_string):
    """ Tenta converter a data para um formato padronizado YYYY-MM-DD para facilitar a ordenação """
    try:
        # A PCSO costuma usar formatos como "M/D/YYYY" ou "MM/DD/YYYY"
        dt = datetime.strptime(date_string.strip(), "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return date_string.strip()

def scrape_pcso_advanced():
    session = requests.Session()
    
    # PASSO 1: Fazer um GET inicial para pegar os tokens de segurança do ASP.NET
    print("Acessando a página para capturar tokens de segurança...")
    try:
        res_inicial = session.get(URL, headers=HEADERS, timeout=15)
        soup_inicial = BeautifulSoup(res_inicial.text, 'html.parser')
        
        viewstate = soup_inicial.find('input', {'name': '__VIEWSTATE'})['value'] if soup_inicial.find('input', {'name': '__VIEWSTATE'}) else ''
        viewstategenerator = soup_inicial.find('input', {'name': '__VIEWSTATEGENERATOR'})['value'] if soup_inicial.find('input', {'name': '__VIEWSTATEGENERATOR'}) else ''
        eventvalidation = soup_inicial.find('input', {'name': '__EVENTVALIDATION'})['value'] if soup_inicial.find('input', {'name': '__EVENTVALIDATION'}) else ''
    except Exception as e:
        print(f"Erro ao capturar tokens: {e}. O layout do site pode ter mudado.")
        return

    # PASSO 2: Montar o payload (simulando que apertamos o botão "Search" para os últimos 30 dias)
    hoje = datetime.now()
    mes_passado = hoje - timedelta(days=30)
    
    # Nota: Os nomes dos campos (ctl00$...) podem variar no site deles. 
    # Abaixo é a estrutura padrão de WebForms. Se falhar, faremos o parse da tabela inicial.
    payload = {
        '__VIEWSTATE': viewstate,
        '__VIEWSTATEGENERATOR': viewstategenerator,
        '__EVENTVALIDATION': eventvalidation,
        # Muitas vezes, submeter os tokens vazios já força o servidor a carregar os últimos dias
        'ctl00$ctl00$cphContainer$cpContent$ddlStartMonth': mes_passado.strftime('%B'),
        'ctl00$ctl00$cphContainer$cpContent$ddlStartYear': mes_passado.strftime('%Y'),
        'ctl00$ctl00$cphContainer$cpContent$ddlEndMonth': hoje.strftime('%B'),
        'ctl00$ctl00$cphContainer$cpContent$ddlEndYear': hoje.strftime('%Y'),
        'ctl00$ctl00$cphContainer$cpContent$btnSearch': 'Search Lotto'
    }

    print("Buscando dados históricos...")
    try:
        # Fazer o POST para pegar a tabela completa
        res_post = session.post(URL, data=payload, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(res_post.text, 'html.parser')
        
        table = soup.find('table')
        if not table:
            print("Tabela não encontrada no resultado da busca.")
            return

        rows = table.find_all('tr')[1:] # Pula o cabeçalho
        
        # Dicionários para agrupar os jogos
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
                
                # Só adiciona se os números foram extraídos corretamente
                if matriz_numeros:
                    jogos_dict[nome_jogo].append({
                        "date": data_str,
                        "combination_str": combinacao_str,
                        "combination_array": matriz_numeros,
                        "jackpot": jackpot,
                        "winners": vencedores
                    })

        # PASSO 3: Estruturar o JSON Final (UI + Análise)
        json_final = {
            "metadata": {
                "last_updated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "PCSO Official"
            },
            "ui_results": {},   # Para a tela de Resultados
            "analysis_data": {} # Para o Backtesting/Estatísticas
        }

        # Filtrar os top 10 mais recentes de cada jogo
        for jogo, resultados in jogos_dict.items():
            # Ordena por data decrescente (mais recente primeiro)
            resultados.sort(key=lambda x: x['date'], reverse=True)
            top_10 = resultados[:10]

            # 1. Montar os dados visuais para a UI
            json_final["ui_results"][jogo] = [
                {
                    "date": r["date"],
                    "numbers": r["combination_str"],
                    "jackpot": r["jackpot"],
                    "winners": r["winners"]
                } for r in top_10
            ]

            # 2. Montar matriz limpa para matemática pesada (LotoLab)
            json_final["analysis_data"][jogo] = [r["combination_array"] for r in top_10]

        # Salvar o arquivo localmente
        with open('pcso_master_data.json', 'w', encoding='utf-8') as f:
            json.dump(json_final, f, ensure_ascii=False, indent=4)
            
        print(f"Sucesso! Dados processados e salvos. Jogos encontrados: {len(jogos_dict.keys())}")

    except Exception as e:
        print(f"Erro durante o processamento: {e}")

if __name__ == "__main__":
    scrape_pcso_advanced()
