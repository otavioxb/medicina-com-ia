async function carregarProfissoes() {
    const select = document.getElementById("profissao");
    if (!select) return;

    try {
        const response = await fetch("/catalog/profissoes");
        if (!response.ok) {
            throw new Error(`Falha ao carregar profissões: HTTP ${response.status}`);
        }
        const data = await response.json();
        const profissoes = Array.isArray(data.profissoes) ? data.profissoes : [];

        select.innerHTML = '<option value="" disabled selected>Selecione</option>';
        profissoes.forEach((profissao) => {
            const option = document.createElement("option");
            option.value = profissao;
            option.textContent = profissao;
            select.appendChild(option);
        });
        select.disabled = profissoes.length === 0;
    } catch (error) {
        console.error("Erro ao carregar profissões:", error);
        select.innerHTML = '<option value="" disabled selected>Erro ao carregar profissões</option>';
        select.disabled = true;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    carregarProfissoes();
});

document.getElementById('cadastroForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const token = document.getElementById('token').value;
    const usuario = {
        nome: document.getElementById('nome').value,
        cpf: document.getElementById('cpf').value,
        email: document.getElementById('email').value,
        senha: document.getElementById('senha').value,
        data_nascimento: document.getElementById('data_nascimento').value,
        profissao: document.getElementById('profissao').value
    };

    const payload = {
        token: token,
        usuario: usuario,
    };
    console.log("Payload enviado novo:", JSON.stringify(payload, null, 2));

    const mensagemDiv = document.getElementById('mensagem');

    try {
        const response = await fetch('/cadastro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            mensagemDiv.innerHTML = `<div class="alert alert-success">Cadastro realizado com sucesso! Bem-vindo, ${result.nome}.</div>`;
            window.scrollTo({ top: 0, behavior: 'smooth' });
            document.getElementById("cadastroForm").reset();

            if (result.redirect) {
                setTimeout(() => {
                    window.location.href = result.redirect;
                }, 2000);
            }
        } else {
            try {
                const error = await response.json();
                mensagemDiv.innerHTML = `<div class="alert alert-danger">Erro: ${error.detail || "Erro ao processar cadastro."}</div>`;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } catch (e) {
                const errorText = await response.text();
                mensagemDiv.innerHTML = `<div class="alert alert-danger">Erro inesperado: ${errorText}</div>`;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
    } catch (error) {
        console.error('Erro ao enviar dados:', error);
        mensagemDiv.innerHTML = '<div class="alert alert-danger">Erro na requisição. Verifique sua conexão com a internet.</div>';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});
