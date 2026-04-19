from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
import sys

URL = "https://www.pcso.gov.ph/searchlottoresult.aspx"

def clean_numbers(number_string):
    return [int(n) for n in re.findall(r'\d+', number_string)]

def parse_date(date_string):
    try:
        dt = datetime.strptime(date_string.strip(), "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except:
        return date_string.strip()

def scrape_pcso_playwright():
    print("Iniciando o navegador fantasma (Playwright)...")
    with sync_playwright() as p:
        # Lança o navegador Chromium invisível
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("Passo 1: Acessando o site oficial da PCSO...")
            # Timeout longo (60s) porque o site deles às vezes demora a responder
            page.goto(URL, timeout=60000)
            
            print("Passo 2: Selecionando o período de busca...")
            hoje = datetime.now()
            mes_passado = hoje - timedelta(days=30)
            
            # Usamos locators que procuram elementos cujo ID termina ($=) com o nome correto
            page.locator("select[id$='ddlStartMonth']").select_option(label=mes_passado.strftime('%B'))
            page.locator("select[id$='ddlStartYear']").select_option(label=mes_passado.strftime('%Y'))
            
            page.locator("select[id$='ddlEndMonth']").select_option(label=hoje.strftime('%B'))
            page.locator("select[id$='ddlEndYear']").select_option(label=hoje.strftime('%Y'))

            print("Passo 3: Clicando em Search e aguardando o carregamento...")
            page.locator("input[id$='btnSearch']").click()
            
            # O bot pausa e só continua quando a tabela aparecer na tela (ignora bloqueios de delay do servidor)
            page.wait_for_selector("table", timeout=30000)
            
            print("Passo 4: HTML gerado com sucesso. Extraindo dados...")
            html = page.content()
            
        except Exception as e:
            print(f"Erro de navegação: {e}")
            browser.close()
            sys.exit(1)
            
        browser.close()

        # Agora passamos o HTML perfeito e renderizado para o BeautifulSoup mastigar
        print("Passo 5: Organizando informações...")
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print("ERRO CRÍTICO: Tabela sumiu do HTML.")
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
             print("ERRO: A tabela está vazia.")
             sys.exit(1)

        print("Passo 6: Estruturando JSON (UI + Análise)...")
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
            
        print(f"Sucesso absoluto! JSON atualizado com os dados de {len(jogos_dict.keys())} jogos.")

if __name__ == "__main__":
    scrape_pcso_playwright()
