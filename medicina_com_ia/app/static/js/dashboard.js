const nome = localStorage.getItem('nome');
const profissao = localStorage.getItem('profissao');

let primeiroNome = "";
if (nome) {
    primeiroNome = nome.split(" ")[0];
}
document.getElementById("nomeUsuario").textContent = primeiroNome;
const avatarEl = document.getElementById("avatarInitial");
if (avatarEl && primeiroNome) {
    avatarEl.textContent = primeiroNome.charAt(0).toUpperCase();
}
const sidebarNomeEl = document.getElementById("sidebarNome");
if (sidebarNomeEl) sidebarNomeEl.textContent = nome || '';
const sidebarProfEl = document.getElementById("sidebarProfissao");
if (sidebarProfEl) sidebarProfEl.textContent = profissao || '';
let consultasPendentes = [];

// verificarSessaoPeriodicamente(); 

document.addEventListener("DOMContentLoaded", () => {
  const sessao_id = sessionStorage.getItem('sessao_id');
  if (!sessao_id) {
    window.location.href = "/login";
    return;
  }

  carregarDashboard(sessao_id);

  document.getElementById('novaConsultaBtn').addEventListener('click', () => {
    window.location.href = "/";
  });

  document.getElementById('logoutBtn').addEventListener('click', () => {
    const sessao_id = sessionStorage.getItem('sessao_id');
    if (sessao_id) {
      fetch('/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sessao_id })
      })
      .finally(() => {
        sessionStorage.clear();
        localStorage.clear();
        window.location.href = "/login";
      });
    } else {
      sessionStorage.clear();
      localStorage.clear();
      window.location.href = "/login";
    }
  });

  document.getElementById('retomarBtn').addEventListener('click', () => {
    const sessao_id = sessionStorage.getItem('sessao_id_retomada');
    const patient_id = sessionStorage.getItem('patient_id_retomada');
    const necessidade = sessionStorage.getItem('necessidade_retomada');
    if (sessao_id && patient_id && necessidade) {
      sessionStorage.setItem('sessao_id', sessao_id);
      sessionStorage.setItem('patient_id', patient_id);
      sessionStorage.setItem('necessidade', necessidade);
      window.location.href = "/";
    } else {
      alert('Nao foi possivel retomar a sessao.');
    }
  });

  document.getElementById('descartarBtn').addEventListener('click', async () => {
    const sessao_id = sessionStorage.getItem('sessao_id_retomada');
    try {
      const response = await fetch(`/descartar_consulta?sessao_id=${sessao_id}`, { method: 'DELETE' });
      const result = await response.json();
      if (result.status === 'success') {
        document.getElementById('retomarConsultaAlerta').classList.add('d-none');
        sessionStorage.removeItem('sessao_id_retomada');
        sessionStorage.removeItem('patient_id_retomada');
        sessionStorage.removeItem('necessidade_retomada');
        alert('Sessao descartada com sucesso.');
        carregarDashboard(sessao_id);
      } else {
        alert('Erro ao descartar a sessao.');
      }
    } catch (error) {
      console.error("Erro ao descartar consulta:", error);
      alert('Erro inesperado.');
    }
  });
});


async function carregarDashboard(sessao_id) {
  try {
    const response = await fetch(`/dashboard_data?sessao_id=${sessao_id}`);
    const data = await response.json();

    // Atualize as estatísticas normalmente
    document.getElementById('totalConsultas').innerText = data.totalConsultas ?? '--';
    document.getElementById('tempoTranscrito').innerText = data.tempoTranscrito ?? '--';
    document.getElementById('tempoMedio').innerText = data.tempoMedio ?? '--';
    document.getElementById('mesMaisConsultas').innerText = data.mesMaisConsultas ?? '--';

    // Zere o array a cada carregamento
    consultasPendentes = [];

    if (data.consultasPendentes && data.consultasPendentes.length > 0) {
      document.getElementById('tabelaRetomada').classList.remove('d-none');
      document.getElementById('btnDescartarTodas').classList.remove('d-none');
      const pendingCountEl = document.getElementById('pendingCount');
      if (pendingCountEl) pendingCountEl.textContent = data.consultasPendentes.length;
      const tbody = document.getElementById('tbodyRetomada');
      tbody.innerHTML = "";
      data.consultasPendentes.forEach(consulta => {
        // Preencha o array global com os identificadores para "descartar todas"
        consultasPendentes.push({
          sessao_id: consulta.sessao_id,
          patient_id: consulta.patient_id,
          necessidade: consulta.necessidade
        });
        // Cria a linha normalmente
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${consulta.updated_at}</td>
          <td>${consulta.paciente}</td>
          <td>${consulta.necessidade}</td>
          <td>
            <button class="btn btn-sm btn-success" onclick="baixarRelatorio('${consulta.sessao_id}', '${consulta.patient_id}', '${consulta.necessidade}')">Retomar</button>
            <button class="btn btn-sm btn-danger" onclick="descartarConsulta('${consulta.sessao_id}', '${consulta.patient_id}', '${consulta.necessidade}')">Descartar</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } else {
      document.getElementById('tabelaRetomada').classList.add('d-none');
      document.getElementById('btnDescartarTodas').classList.add('d-none');
    }

  } catch (error) {
    console.error("Erro ao carregar dados do dashboard:", error);
  }
}

async function baixarRelatorio(sessao_id, patient_id, necessidade,profissao) {
  try {
    mostrarModalProgresso();
    const url = `/retomar_relatorio?sessao_id=${sessao_id}&patient_id=${patient_id}&necessidade=${necessidade}&profissao=${profissao}`; 

    const response = await fetch(url);
    if (!response.ok) throw new Error('Erro ao baixar relatório!');

    // Extrai o nome do arquivo do header
    const contentDisposition = response.headers.get('Content-Disposition');
    let suggestedFilename = "Relatorio.docx";
    if (contentDisposition) {
      // Primeiro tenta o padrão RFC 5987 (filename*=)
      let match = contentDisposition.match(/filename\*=UTF-8''(.+)/);
      if (match && match[1]) {
        suggestedFilename = decodeURIComponent(match[1]);
      } else {
        // Depois tenta o padrão tradicional (filename=)
        match = contentDisposition.match(/filename="?([^\";]+)"?/);
        if (match && match[1]) {
          suggestedFilename = match[1];
        }
      }
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = suggestedFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);

    esconderModalProgresso();
    setTimeout(() => location.reload(), 500);

  } catch (err) {
    alert(err.message || 'Erro inesperado no download.');
    esconderModalProgresso();
  }
}

async function descartarConsulta(sessao_id, patient_id, necessidade) {
  if (!confirm('Deseja realmente descartar esta sessao?')) return;
  try {
    const url = `/descartar_consulta?sessao_id=${encodeURIComponent(sessao_id)}&patient_id=${encodeURIComponent(patient_id)}&necessidade=${encodeURIComponent(necessidade)}`;
    const response = await fetch(url, { method: 'DELETE' });
    const result = await response.json();
    if (result.message && result.message.includes("sucesso")) {
      alert('Sessao descartada com sucesso.');
      location.reload();
    } else {
      alert('Erro ao descartar a sessao.');
    }
  } catch (error) {
    console.error("Erro ao descartar consulta:", error);
    alert('Erro inesperado.');
  }
}

function mostrarModalProgresso() {
  new bootstrap.Modal(document.getElementById('modalProgresso')).show();
}

function esconderModalProgresso() {
  const modal = bootstrap.Modal.getInstance(document.getElementById('modalProgresso'));
  if (modal) modal.hide();
}

async function descartarTodasConsultas() {
  if (!confirm('Deseja realmente descartar todas as sessoes pendentes?')) return;

  for (const c of consultasPendentes) {
    try {
      // Chama sua rota de descarte individual
      await fetch(`/descartar_consulta?sessao_id=${encodeURIComponent(c.sessao_id)}&patient_id=${encodeURIComponent(c.patient_id)}&necessidade=${encodeURIComponent(c.necessidade)}`, {
        method: 'DELETE'
      });
      // Se sua rota precisar de "necessidade" também, acrescente na URL!
      // Exemplo: ...&necessidade=${encodeURIComponent(c.necessidade)}
    } catch (err) {
      console.error("Erro ao descartar consulta:", err, c);
    }
  }

  alert('Todas as sessoes pendentes foram descartadas.');
  location.reload();
}

// function verificarSessaoPeriodicamente() {
//   setInterval(async () => {
//     const sessao_id = sessionStorage.getItem('sessao_id');
//     try {
//       const response = await fetch(`/verificar_sessao?sessao_id=${sessao_id}`);
//       if (!response.ok) {
//         exibirToastDesconexao();
//         setTimeout(() => {
//           window.location.href = "/login";
//         }, 4000);
//       }
//     } catch (error) {
//       console.error("Erro ao verificar sessão:", error);
//       exibirToastDesconexao();
//       setTimeout(() => {
//         window.location.href = "/login";
//       }, 4000);
//     }
//   }, 2 * 60 * 1000); // verifica a cada 2 minutos
// }

// function exibirToastDesconexao(msg = "Sua sessão foi desconectada. Redirecionando para login...") {
//   const toastHTML = `
//     <div id="ws-disconnect-toast" class="toast align-items-center text-bg-danger border-0 show" role="alert" aria-live="assertive" aria-atomic="true" style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;">
//       <div class="d-flex">
//         <div class="toast-body">
//           ${msg}
//         </div>
//         <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
//       </div>
//     </div>
//   `;

//   const existingToast = document.getElementById('ws-disconnect-toast');
//   if (existingToast) existingToast.remove();

//   const toastContainer = document.createElement('div');
//   toastContainer.innerHTML = toastHTML;
//   document.body.appendChild(toastContainer);
// }