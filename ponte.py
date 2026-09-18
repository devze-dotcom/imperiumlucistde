"""Ponte Serial-HTTP para captura e encaminhamento de dados do Arduino.

Escuta leituras na porta serial '/dev/ttyUSB0' e encaminha via POST
para o backend Flask em 'http://localhost:8080/api/sensor'.
"""

import sys
import time
import requests
import serial

# Configurações da Conexão Serial
PORTA_SERIAL = '/dev/ttyUSB0'
BAUD_RATE = 9600
SERIAL_TIMEOUT = 2.0  # segundos

# Configurações da API de Destino
URL_API = 'http://localhost:8080/api/sensor'
SENSOR_ID = 'sensor_porta'
HTTP_TIMEOUT = 3.0  # segundos


def executar_ponte():
    arduino = None

    try:
        print(f"Tentando conectar ao Arduino em {PORTA_SERIAL} a {BAUD_RATE} baud...")
        arduino = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        
        # Aguarda 2 segundos para estabilização da conexão e reinicialização do Arduino
        time.sleep(2.0)
        print(f"Conexão serial estabelecida com sucesso em {PORTA_SERIAL}.")
        print(f"Encaminhando leituras para {URL_API} (Pressione Ctrl+C para encerrar)...\n")

        while True:
            # Lê uma linha enviada pelo Arduino
            linha_bruta = arduino.readline().decode('utf-8', errors='replace').strip()

            # Se a linha estiver vazia (ex: timeout da leitura), continua o loop
            if not linha_bruta:
                continue

            # Tratamento de exceção para conversão do dado e descarte de ruído
            try:
                distancia = float(linha_bruta)
            except ValueError:
                # Ignora ruídos na transmissão serial ou leituras malformadas
                continue

            payload = {
                "sensorId": SENSOR_ID,
                "distancia": distancia
            }

            try:
                resposta = requests.post(URL_API, json=payload, timeout=HTTP_TIMEOUT)
                if resposta.status_code == 200:
                    print(f"[OK] Distância: {distancia:.2f} cm -> Enviado para API (Status 200)")
                else:
                    print(f"[AVISO] Resposta inesperada da API: Status {resposta.status_code}")
            except requests.exceptions.RequestException as err:
                print(f"[FALHA DE REDE] Não foi possível conectar à API: {err}")

    except serial.SerialException as err:
        print(f"\n[ERRO SERIAL] Não foi possível acessar a porta {PORTA_SERIAL}: {err}")
        print("Dicas de verificação:")
        print(" 1. Verifique se o cabo USB do Arduino está conectado firmemente.")
        print(" 2. Confirme o nome da porta com o comando: ls /dev/tty*")
        print(" 3. Certifique-se de que seu usuário tem permissão na porta: sudo usermod -a -G dialout $USER")
    except KeyboardInterrupt:
        print("\nInterrupção solicitada pelo usuário (Ctrl+C). Encerrando serviço...")
    except Exception as err:
        print(f"\n[ERRO INESPERADO] {err}")
    finally:
        # Garante que a conexão serial seja sempre fechada de forma segura
        if arduino and arduino.is_open:
            arduino.close()
            print(f"Conexão com {PORTA_SERIAL} fechada com sucesso.")


if __name__ == '__main__':
    executar_ponte()
