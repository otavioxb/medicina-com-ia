from fastapi import APIRouter, HTTPException

from app.modules.prompt_catalog import catalogo_profissoes_necessidades, carregar_prompts

router = APIRouter()


@router.get("/catalog/profissoes")
def get_catalogo_profissoes():
    try:
        catalogo = catalogo_profissoes_necessidades()
        _, prompts_path = carregar_prompts()
        return {
            "profissoes": list(catalogo.keys()),
            "necessidades_por_profissao": catalogo,
            "prompts_path": prompts_path,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao carregar catálogo de profissões: {exc}"
        )
