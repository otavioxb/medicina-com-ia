document.getElementById('cadastroForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const token = document.getElementById('token').value;  // campo que você deve incluir no HTML
    const usuario = {
        nome: document.getElementById('nome').value,
        cpf: document.getElementById('cpf').value,
        email: document.getElementById('email').value,
        senha: document.getElementById('senha').value,
        data_nascimento: document.getElementById('data_nascimento').value,
        profissao: document.getElementById('profissao').value
    };

    // const cartao = {
    //     nome_cartao: document.getElementById('nome_cartao').value,
    //     numero_mascarado: document.getElementById('numero_mascarado').value,
    //     validade: document.getElementById('validade').value,
    //     bandeira: document.getElementById('bandeira').value
    // };

    const payload = {
        token: token,         // <- ESSENCIAL!
        usuario: usuario,
        // cartao: cartao
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
            // Tenta extrair JSON do erro
            try {
                const error = await response.json();
                mensagemDiv.innerHTML = `<div class="alert alert-danger">Erro: ${error.detail || "Erro ao processar cadastro."}</div>`;
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } catch (e) {
                // Se não for JSON, tenta mostrar texto
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