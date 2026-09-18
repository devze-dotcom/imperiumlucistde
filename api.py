"""Servidor Backend Flask para recepção e monitoramento de telemetria de sensores."""

import time
from collections import deque
from datetime import datetime
from threading import Lock
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Lock para garantir concorrência segura entre threads do Flask
dados_lock = Lock()

# Estado global da telemetria
telemetria = {
    "sensorId": None,
    "distancia": None,
    "timestamp": None,
    "ultimo_registro_epoch": None,
    "total_leituras": 0,
    "min_distancia": None,
    "max_distancia": None,
    "soma_distancia": 0.0
}

# Buffer circular com as últimas 40 medições para gráficos e tabela
historico = deque(maxlen=40)

# Estrutura em memória temporária para rastreamento de estado por sensor
# Armazena por sensorId:
# - "historico": deque(maxlen=5) com as últimas 5 distâncias
# - "timestamp": timestamp exato (time.time()) da última leitura recebida
# - "media_anterior": float com a última média móvel calculada
sensores_estado = {}


def calcular_media_suavizada(amostras):
    """Calcula a média móvel descartando extremos (outliers) para amenizar ruídos do HC-SR04."""
    if not amostras:
        return 0.0

    valores = list(amostras)
    # Se houver 3 ou mais leituras, descarta o menor e o maior valor (trimmed mean)
    if len(valores) >= 3:
        valores_ordenados = sorted(valores)
        valores_filtrados = valores_ordenados[1:-1]
        return round(sum(valores_filtrados) / len(valores_filtrados), 2)

    return round(sum(valores) / len(valores), 2)


@app.route('/')
def index():
    """Renderiza o painel visual (frontend) em HTML/CSS/JS."""
    return render_template('index.html')


@app.route('/api/sensor', methods=['GET', 'POST'])
def rota_sensor():
    """Gerencia recepção (POST) da ponte serial e consulta (GET) do frontend."""
    global telemetria

    if request.method == 'POST':
        dados = request.get_json(silent=True)

        if not dados or not isinstance(dados, dict):
            return jsonify({
                "status": "erro",
                "mensagem": "Payload inválido. Esperado JSON."
            }), 400

        sensor_id = dados.get("sensorId")
        distancia = dados.get("distancia")

        if sensor_id is None or distancia is None:
            return jsonify({
                "status": "erro",
                "mensagem": "Campos obrigatórios: 'sensorId' e 'distancia'."
            }), 400

        try:
            distancia = round(float(distancia), 2)
        except (ValueError, TypeError):
            return jsonify({
                "status": "erro",
                "mensagem": "Campo 'distancia' deve ser numérico."
            }), 400

        agora = datetime.now()
        timestamp_formatado = agora.strftime("%H:%M:%S")
        epoch_atual = time.time()

        # Atualiza os dados em memória de maneira thread-safe
        with dados_lock:
            # 1. Inicializa ou recupera a estrutura de estado do sensor
            if sensor_id not in sensores_estado:
                sensores_estado[sensor_id] = {
                    "historico": deque(maxlen=5),
                    "timestamp": None,
                    "media_anterior": None
                }

            estado = sensores_estado[sensor_id]
            timestamp_anterior = estado["timestamp"]
            media_anterior = estado["media_anterior"]

            # Média Móvel: Adiciona distância atual mantendo no máximo 5 itens
            estado["historico"].append(distancia)
            distancia_suavizada = calcular_media_suavizada(estado["historico"])

            # Velocidade: delta espaço / delta tempo em cm/s e determinação da direção
            if timestamp_anterior is None or media_anterior is None:
                # Primeiro POST: robustez quando não há dados anteriores para comparar
                velocidade_cm_por_segundo = 0.0
                direcao = "parado"
            else:
                delta_tempo = epoch_atual - timestamp_anterior
                delta_espaco = distancia_suavizada - media_anterior

                if delta_tempo <= 0:
                    velocidade_cm_por_segundo = 0.0
                    direcao = "parado"
                else:
                    velocidade_bruta = abs(delta_espaco) / delta_tempo
                    velocidade_cm_por_segundo = round(velocidade_bruta, 2)

                    # Tolerância para eliminar ruídos residuais em repouso
                    if velocidade_cm_por_segundo == 0.0 or abs(delta_espaco) < 0.01:
                        direcao = "parado"
                        velocidade_cm_por_segundo = 0.0
                    elif delta_espaco < 0:
                        direcao = "aproximando"
                    else:
                        direcao = "afastando"

            # Atualiza os dados de timestamp e média na memória para a próxima iteração
            estado["timestamp"] = epoch_atual
            estado["media_anterior"] = distancia_suavizada

            # Atualiza telemetria global e buffer visual do dashboard
            telemetria["sensorId"] = sensor_id
            telemetria["distancia"] = distancia_suavizada
            telemetria["timestamp"] = timestamp_formatado
            telemetria["ultimo_registro_epoch"] = epoch_atual
            telemetria["total_leituras"] += 1
            telemetria["soma_distancia"] += distancia

            if telemetria["min_distancia"] is None or distancia < telemetria["min_distancia"]:
                telemetria["min_distancia"] = distancia

            if telemetria["max_distancia"] is None or distancia > telemetria["max_distancia"]:
                telemetria["max_distancia"] = distancia

            historico.append({
                "sensorId": sensor_id,
                "distancia": distancia_suavizada,
                "distancia_pura": distancia,
                "velocidade": velocidade_cm_por_segundo,
                "direcao": direcao,
                "timestamp": timestamp_formatado,
                "epoch": epoch_atual
            })

        # Exibição no terminal para acompanhamento
        print(f"[{timestamp_formatado}] Sensor: {sensor_id} | Distância Pura: {distancia:.2f} cm | Suavizada: {distancia_suavizada:.2f} cm | Vel: {velocidade_cm_por_segundo:.2f} cm/s | Dir: {direcao}")

        return jsonify({
            "status": "sucesso",
            "distancia_pura": float(distancia),
            "distancia_suavizada": float(distancia_suavizada),
            "velocidade_cm_por_segundo": float(velocidade_cm_por_segundo),
            "direcao": direcao
        }), 200

    # Método GET: Consulta dos dados pelo Frontend
    with dados_lock:
        epoch_agora = time.time()
        ultimo_epoch = telemetria.get("ultimo_registro_epoch")
        segundos_desde_ultimo = (epoch_agora - ultimo_epoch) if ultimo_epoch else None
        
        # Considerado online se enviou leitura nos últimos 4 segundos
        online = (segundos_desde_ultimo is not None and segundos_desde_ultimo <= 4.0)

        total = telemetria["total_leituras"]
        media = round(telemetria["soma_distancia"] / total, 2) if total > 0 else 0.0

        return jsonify({
            "status": "sucesso",
            "online": online,
            "segundos_desde_ultimo": round(segundos_desde_ultimo, 1) if segundos_desde_ultimo else None,
            "atual": {
                "sensorId": telemetria["sensorId"],
                "distancia": telemetria["distancia"],
                "timestamp": telemetria["timestamp"]
            },
            "estatisticas": {
                "total": total,
                "min": telemetria["min_distancia"],
                "max": telemetria["max_distancia"],
                "media": media
            },
            "historico": list(historico)
        }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Servidor de Telemetria iniciado com sucesso!")
    print("📍 Painel Web: http://localhost:8080/")
    print("📡 Endpoint API: http://localhost:8080/api/sensor")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8080, debug=True)