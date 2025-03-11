from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, conlist
import mysql.connector
from dotenv import load_dotenv
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

@app.post("/evaluar-propuestas/", response_model=list[EmpresaSeleccionada])
async def evaluar_propuestas(solicitud: SolicitudPropuestas):
    competidores_ids = [c.id_competidor for c in solicitud.competidores]
    
    # Consultar MySQL para obtener datos históricos
    propuestas_bd = consultar_propuestas(competidores_ids)
    if not propuestas_bd:
        raise HTTPException(status_code=404, detail="No se encontraron datos para los competidores dados.")
    
    # Determinar 'n' según la cantidad de competidores
    # Determinar 'n' según la cantidad de competidores
    num_competidores = len(solicitud.competidores)
    if num_competidores == 3:
        n = 2
    elif num_competidores in [4, 5]:
        n = 3
    elif num_competidores >= 6:
        n = 4
    else:
        n = 2  # Valor por defecto

    
    resultados = []
    for prop in propuestas_bd:
        comp_input = next((c for c in solicitud.competidores if c.id_competidor == prop['id_competidor']), None)
        if comp_input:
            puntaje = calcular_puntaje(comp_input.propuesta_economica, prop['veces_ganadas'], prop['veces_participadas'])
            resultados.append({
                "id_competidor": prop['id_competidor'],
                "propuesta_economica": comp_input.propuesta_economica,
                "puntaje": puntaje
            })
    
    # Ordenar por puntaje y seleccionar los mejores 'n'
    resultados.sort(key=lambda x: x["puntaje"], reverse=True)
    return resultados[:n]
