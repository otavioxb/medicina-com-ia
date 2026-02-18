function togglePassword() {
  const input = document.getElementById('senha');
  const icon = document.getElementById('toggleIcon');
  if (input.type === 'password') {
    input.type = 'text';
    icon.classList.replace('bi-eye', 'bi-eye-slash');
  } else {
    input.type = 'password';
    icon.classList.replace('bi-eye-slash', 'bi-eye');
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const loginForm = document.getElementById("loginForm");
  const loginMessage = document.getElementById("loginMessage");
  const loginBtn = document.getElementById("loginBtn");

  loginForm.onsubmit = async function (event) {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const senha = document.getElementById("senha").value.trim();

    loginBtn.disabled = true;
    loginBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Entrando...';

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
        loginMessage.className = "alert alert-success mt-3";
        loginMessage.innerHTML = '<i class="bi bi-check-circle me-1"></i>' + result.message;
        loginMessage.classList.remove("d-none");

        setTimeout(() => {
          window.location.href = "/dashboard";
        }, 1500);
      } else {
        loginMessage.className = "alert alert-danger mt-3";
        loginMessage.innerHTML = '<i class="bi bi-x-circle me-1"></i>Usuario ou senha incorretos!';
        loginMessage.classList.remove("d-none");
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Entrar';
      }
    } catch (error) {
      console.error("Erro ao tentar logar:", error);
      loginMessage.className = "alert alert-danger mt-3";
      loginMessage.innerHTML = '<i class="bi bi-x-circle me-1"></i>Erro ao conectar com o servidor.';
      loginMessage.classList.remove("d-none");
      loginBtn.disabled = false;
      loginBtn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> Entrar';
    }
  };
});
