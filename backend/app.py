"""API do prototipo de reconhecimento de mesa de poker.

Rodar:
    pip install -r requirements.txt
    python app.py            # ou: uvicorn app:app --host 0.0.0.0 --port 8000
"""
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engines import MOTORES_DISPONIVEIS, obter_motor
from ajuda_acao import avaliar as avaliar_acao

load_dotenv()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
MAX_TAMANHO = 10 * 1024 * 1024  # 10 MB
TIPOS_ACEITOS = {"image/jpeg", "image/png", "image/gif", "image/webp"}

app = FastAPI(title="Poker Foto Reconhecimento", version="0.1.0")


class FrontendFiles(StaticFiles):
    """Serve os arquivos do frontend sem cache, para facilitar iteracao."""

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-store"
        return resp


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "motores_disponiveis": list(MOTORES_DISPONIVEIS),
        "motor_padrao": os.getenv("MOTOR_RECONHECIMENTO", "gemini"),
        "api_key_configurada": bool(os.getenv("ANTHROPIC_API_KEY")),
        "modelo_anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        "gemini_key_configurada": bool(os.getenv("GEMINI_API_KEY")),
        "modelo_gemini": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    }


@app.post("/api/reconhecer")
async def reconhecer(
    arquivo: UploadFile = File(...),
    motor: str | None = Query(default=None, description="mock | anthropic"),
    debug: bool = Query(default=False, description="Inclui metadados de debug na resposta"),
):
    if arquivo.content_type not in TIPOS_ACEITOS:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de arquivo '{arquivo.content_type}' nao suportado. Use JPEG/PNG/WebP.",
        )

    imagem_bytes = await arquivo.read()
    if len(imagem_bytes) > MAX_TAMANHO:
        raise HTTPException(status_code=413, detail="Imagem muito grande (maximo 10 MB).")
    if not imagem_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    motor_pedido = motor
    motor_usado = motor_pedido
    nota_fallback = None

    try:
        engine = obter_motor(motor_pedido)
        motor_usado = engine.nome
    except ValueError as exc:
        if motor_pedido is not None:
            raise HTTPException(status_code=400, detail=str(exc))
        engine = obter_motor("mock")
        motor_usado = "mock"
        nota_fallback = str(exc)

    try:
        inicio = time.perf_counter()
        resultado = engine.reconhecer(imagem_bytes, arquivo.content_type)
        tempo_ms = round((time.perf_counter() - inicio) * 1000)
    except ValueError as exc:  # ex: motor pedido sem chave configurada
        engine = obter_motor("mock")
        resultado = engine.reconhecer(imagem_bytes, arquivo.content_type)
        nota_fallback = f"Motor '{motor_usado}' indisponivel: {exc}. Usado mock."
        motor_usado = "mock"
        tempo_ms = 0
    except Exception as exc:  # erro da API do motor (chave invalida, rede, etc.)
        raise HTTPException(
            status_code=502,
            detail=f"Falha no motor '{engine.nome}': {exc}",
        ) from exc

    resultado["motor_usado"] = motor_usado
    resultado["tempo_ms"] = tempo_ms
    resultado["motor_pedido"] = motor_pedido
    resultado["acao_sugerida"] = avaliar_acao(resultado)
    if nota_fallback:
        resultado["nota_fallback"] = nota_fallback
        obs = (resultado.get("observacoes") or "") + f" [{nota_fallback}]"
        resultado["observacoes"] = obs.strip()

    if not debug:
        resultado.pop("tempo_ms", None)

    return resultado


app.mount("/", FrontendFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
