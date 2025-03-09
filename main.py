from fastapi import FastAPI
from pydantic import BaseModel, conlist
from database import consultar_propuestas

app = FastAPI()

# Definiciones claras del esquema esperado en la solicitud
class Competidor(BaseModel):
    id_competidor: int
    propuesta_economica: float

class SolicitudPropuestas(BaseModel):
    licitacion_id: int
    competidores: conlist(Competidor, min_length=1)

class EmpresaSeleccionada(BaseModel):
    id_competidor: int
    propuesta_economica: float
    puntaje: float  # resultado de tu fórmula

@app.post("/evaluar-propuestas/", response_model=list[EmpresaSeleccionada])
async def evaluar_propuestas(solicitud: SolicitudPropuestas):
    competidores_ids = [c.id_competidor for c in solicitud.competidores]

    # Consultar MySQL
    propuestas_bd = consultar_propuestas(solicitud.licitacion_id, competidores_ids)

    # Aquí combinas los datos recibidos con los consultados en la base
    resultados = []
    for prop in propuestas_bd:
        comp_input = next((c for c in solicitud.competidores if c.id_competidor == prop['id_competidor']), None)
        if comp_input:
            # Aplica tu fórmula personalizada aquí
            puntaje = calcular_puntaje(comp_input.propuesta_economica, prop['propuesta_economica'])
            resultados.append({
                "id_competidor": prop['id_competidor'],
                "propuesta_economica": prop['propuesta_economica'],
                "puntaje": puntaje
            })

    # Ordenar resultados según puntaje y retornar hasta 4 empresas
    resultados.sort(key=lambda x: x["puntaje"], reverse=True)

    return resultados[:4]

# Ejemplo de implementación sencilla de la fórmula
def calcular_puntaje(propuesta_usuario, propuesta_bd):
    # Personaliza esta lógica según tu algoritmo real
    # Ejemplo: puntaje basado en diferencia porcentual entre propuestas
    diferencia = abs(propuesta_usuario - propuesta_bd)
    puntaje = max(0, 100 - diferencia)  # Ejemplo simplificado
    return puntaje
