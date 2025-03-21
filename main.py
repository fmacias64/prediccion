from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, conlist
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
import json
import os

# Cargar variables de entorno desde un archivo .env
load_dotenv("config.env")

app = FastAPI()

# Configuración de la base de datos obtenida desde variables de entorno
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": "utf8mb4"
}

# Modelos de solicitud y respuesta
class Competidor(BaseModel):
    id_competidor: int
    propuesta_economica: float

class SolicitudPropuestas(BaseModel):
    licitacion_id: int
    competidores: conlist(Competidor, min_length=1)

class EmpresaSeleccionada(BaseModel):
    id_competidor: int
    propuesta_economica: float
    puntaje: float

# Función para obtener conexión a la base de datos
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# Consulta de propuestas y datos históricos
def consultar_propuestas(competidores_ids):
    query = f'''
        SELECT 
            pyme_id AS id_competidor,
            nombre_empresa,
            veces_participadas,
            veces_ganadas
        FROM empresa_experience 
        WHERE pyme_id IN ({','.join(['%s'] * len(competidores_ids))})
    '''
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query,  competidores_ids)
    resultados = cursor.fetchall()
    conn.close()
    
    return resultados

# Función de cálculo de puntaje basada en experiencia
def calcular_puntaje(propuesta_usuario, veces_ganadas, veces_participadas, alpha=0.7):
    if veces_participadas == 0:
        tasa_exito = 0
    else:
        tasa_exito = veces_ganadas / veces_participadas
    
    score = alpha * (1 / propuesta_usuario) + (1 - alpha) * tasa_exito
    return score
# Función para registrar solicitudes en log_solicitudes
def registrar_log_solicitud(licitacion_id, competidores, consorcios_identificados):
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        INSERT INTO log_solicitudes (licitacion_id, json_concursantes, fecha_hora, consorcios_identificados)
        VALUES (%s, %s, %s, %s)
    '''
    valores = (licitacion_id, json.dumps([c.dict() for c in competidores]), datetime.now(), consorcios_identificados)

    cursor.execute(query, valores)
    conn.commit()
    conn.close()

# Función para registrar consorcios identificados
def registrar_consorcio(licitacion_id, empresas, propuesta_comun):
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        INSERT INTO consorcios_p (licitacion_id, empresas, propuesta_comun)
        VALUES (%s, %s, %s)
    '''
    valores = (licitacion_id, json.dumps(empresas), propuesta_comun)

    cursor.execute(query, valores)
    conn.commit()
    conn.close()

@app.post("/evaluar-propuestas/", response_model=list[EmpresaSeleccionada])
async def evaluar_propuestas(solicitud: SolicitudPropuestas):
    competidores_ids = [c.id_competidor for c in solicitud.competidores]

    # Consultar MySQL para obtener datos históricos
    propuestas_bd = consultar_propuestas(competidores_ids)
    if not propuestas_bd:
        raise HTTPException(status_code=404, detail="No se encontraron datos para los competidores dados.")

    # Determinar 'n'
    num_competidores = len(solicitud.competidores)
    if num_competidores == 3:
        n = 2
    elif num_competidores in [4, 5]:
        n = 3
    elif num_competidores >= 6:
        n = 4
    else:
        n = 2

    resultados = []
    propuestas_dict = {}
    for prop in propuestas_bd:
        comp_input = next((c for c in solicitud.competidores if c.id_competidor == prop['id_competidor']), None)
        if comp_input:
            puntaje = calcular_puntaje(comp_input.propuesta_economica, prop['veces_ganadas'], prop['veces_participadas'])
            resultados.append({
                "id_competidor": prop['id_competidor'],
                "propuesta_economica": comp_input.propuesta_economica,
                "puntaje": puntaje
            })
            # Agrupar propuestas para detectar consorcios
            prop_key = round(comp_input.propuesta_economica, 2)
            propuestas_dict.setdefault(prop_key, []).append(prop['id_competidor'])

    # Identificar y registrar consorcios
    consorcios_identificados = 0
    for propuesta_comun, empresas in propuestas_dict.items():
        if len(empresas) > 1:
            registrar_consorcio(solicitud.licitacion_id, empresas, propuesta_comun)
            consorcios_identificados += 1

    # Registrar log de la solicitud
    registrar_log_solicitud(solicitud.licitacion_id, solicitud.competidores, consorcios_identificados)

    # Ordenar y retornar los mejores 'n'
    resultados.sort(key=lambda x: x["puntaje"], reverse=True)
    return resultados[:n]
