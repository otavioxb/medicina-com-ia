function togglePassword() {
    const input = document.getElementById('senha');
    input.type = input.type === 'password' ? 'text' : 'password';
  }
  
  document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("loginForm");
    const loginMessage = document.getElementById("loginMessage");
  
    loginForm.onsubmit = async function (event) {
      event.preventDefault();
  
      const email = document.getElementById("email").value.trim();
      const senha = document.getElementById("senha").value.trim();
  
      try {
        const response = await fetch("/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, senha }),
        });
  
        if (response.ok) {
          const result = await response.json();
          localStorage.setItem("sessao_id", result.sessao_id);
          sessionStorage.setItem("sessao_id", result.sessao_id);
          localStorage.setItem('nome', result.nome);
          localStorage.setItem('profissao', result.profissao);
          loginMessage.className = "alert alert-success";
          loginMessage.innerText = result.message;
          loginMessage.classList.remove("d-none");
  
          setTimeout(() => {
            window.location.href = "/dashboard";
          }, 1500);
        } else {
          loginMessage.className = "alert alert-danger";
          loginMessage.innerText = "Usuário ou senha incorretos!";
          loginMessage.classList.remove("d-none");
        }
      } catch (error) {
        console.error("Erro ao tentar logar:", error);
        loginMessage.className = "alert alert-danger";
        loginMessage.innerText = "Erro ao conectar com o servidor.";
        loginMessage.classList.remove("d-none");
      }
    };
  });