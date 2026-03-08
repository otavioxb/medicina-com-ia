// JS Principal
let socket;
let isSocketConnected = false;
const sessao_id = localStorage.getItem("sessao_id");
if (!sessao_id || sessao_id === "null" || sessao_id === "undefined") {
    window.location.href = "/login";
}
const profissao = localStorage.getItem('profissao');
let necessidade = "";
let patient_id;
let pollingInterval;
let isRecording = false;
let audioContext;
let inputStream;
let recA = null;
let recB = null;
let scheduleAStartTimeout, scheduleAStopTimeout;
let scheduleBStartTimeout, scheduleBStopTimeout;
let elapsedTime = 0;
let startTime;
let timerInterval;
let statusBannerTimeout = null;

const CHUNK_DURATION_SEC = 8;
const OVERLAP_SEC = 1;
const RECORD_B_START_SEC = CHUNK_DURATION_SEC - OVERLAP_SEC;
const BLOCK_DURATION = 25; // minutos
const BLOCK_DURATION_MS = BLOCK_DURATION * 60 * 1000;
let blockTimeoutId = null;

function showToast(mensagem, tipo = 'info', tempo = 4000) {
  // Gere um ID único para cada toast (caso haja vários ao mesmo tempo)
  const toastId = `toast-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
  const toastHTML = `
    <div id="${toastId}" class="toast align-items-center text-bg-${tipo} border-0 show"
         role="alert" aria-live="assertive" aria-atomic="true"
         style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;">
      <div class="d-flex">
        <div class="toast-body">
          ${mensagem}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
      </div>
    </div>
  `;
  const container = document.createElement('div');
  container.innerHTML = toastHTML;
  document.body.appendChild(container);

  // Remove automaticamente após N ms
  setTimeout(() => {
    const toast = document.getElementById(toastId);
    if (toast) toast.remove();
    if (container.parentNode) container.remove();
  }, tempo);
}

// function conectarWebSocket() {
//     const wsProtocol = location.protocol === "https:" ? "wss" : "ws";
//     socket = new WebSocket(`${wsProtocol}://${window.location.host}/ws?sessao_id=${sessao_id}`);
  
//     socket.onopen = () => {
//       isSocketConnected = true;
//       console.log("WebSocket conectado");
//     };
  
//     socket.onmessage = (event) => {
//       const data = JSON.parse(event.data);
//       tratarMensagemWebSocket(data);
//     };
  
//     socket.onerror = (error) => {
//       console.error("Erro no WebSocket:", error);
//     };
  
//     socket.onclose = async (event) => {
//         console.warn("WebSocket desconectado:", event.code);
//         isSocketConnected = false;

//         exibirToastDesconexao();
//         setTimeout(() => {
//         window.location.href = "/login";
//         }, 4000);
        
//     };
//   }
  
let retryDelay = 1000; // Atraso inicial para reconexão (1s)
const maxDelay = 30000; // Atraso máximo (30s)
let audioBuffer = []; // Buffer para pacotes de áudio
let isIntentionalDisconnect = false; // Flag para desconexões intencionais

function conectarWebSocket() {
    const wsProtocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${wsProtocol}://${window.location.host}/ws?sessao_id=${sessao_id}`);

    socket.onopen = () => {
        isSocketConnected = true;
        console.log("WebSocket conectado");
        retryDelay = 1000; // Reseta o atraso na conexão bem-sucedida
        // Reenvia pacotes em buffer
        audioBuffer.forEach(packet => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify(packet));
            }
        });
        audioBuffer = []; // Limpa o buffer após reenvio
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "ping") {
            socket.send(JSON.stringify({ type: "pong" })); // Responde ao ping do servidor
        } else {
            tratarMensagemWebSocket(data); // Mantém a lógica existente
        }
    };

    socket.onerror = (error) => {
        console.error("Erro no WebSocket:", error);
    };

    socket.onclose = (event) => {
        isSocketConnected = false;
        console.warn("WebSocket desconectado:", event.code, event.reason);

        if (isIntentionalDisconnect) {
            // Desconexão intencional (ex.: logout)
            exibirToastDesconexao();
            setTimeout(() => {
                window.location.href = "/login";
            }, 4000);
            return;
        }

        // Desconexões não intencionais (ex.: código 1006) ou sessão inválida (1008, 4000)
        if (event.code === 1006) {
            console.log("Fechamento anormal, tentando reconectar...");
            exibirToastDesconexao("Tentando reconectar...");
            setTimeout(() => {
                retryDelay = Math.min(retryDelay * 2, maxDelay);
                conectarWebSocket();
            }, retryDelay + Math.random() * 100); // Jitter
        } else if (event.code === 1008 || event.code === 4000) {
            // Sessão inválida ou substituída por nova sessão
            exibirToastDesconexao(event.reason || "Sessão inválida ou substituída");
            setTimeout(() => {
                window.location.href = "/login";
            }, 4000);
        }
    };
}
function exibirToastDesconexao(msg = "Sua sessão foi desconectada. Redirecionando para login...") {
    const toastHTML = `
      <div id="ws-disconnect-toast" class="toast align-items-center text-bg-danger border-0 show" role="alert" aria-live="assertive" aria-atomic="true" style="position: fixed; bottom: 20px; right: 20px; z-index: 9999;">
        <div class="d-flex">
          <div class="toast-body">
            ${msg}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
        </div>
      </div>
    `;
  
    const existingToast = document.getElementById('ws-disconnect-toast');
    if (existingToast) existingToast.remove();
  
    const toastContainer = document.createElement('div');
    toastContainer.innerHTML = toastHTML;
    document.body.appendChild(toastContainer);
}
  
// Captura erros globais de JS e envia ao backend via WebSocket
window.onerror = function (message, source, lineno, colno, error) {
const erroCompleto = `${message} at ${source}:${lineno}:${colno}`;
enviarWebSocket("log_frontend", { mensagem: `ERRO JS: ${erroCompleto}` });
};

// Captura erros não tratados de Promises
window.addEventListener("unhandledrejection", function (event) {
enviarWebSocket("log_frontend", {
    mensagem: `ERRO Promessa não tratada: ${event.reason}`
});
});

function enviarWebSocket(tipo, payload = {}) {
  if (isSocketConnected && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: tipo, payload }));
  } else {
    console.warn("WebSocket não está conectado. Tentando reconectar...");
    conectarWebSocket();
    setTimeout(() => {
      if (isSocketConnected) {
        socket.send(JSON.stringify({ type: tipo, payload }));
      }
    }, 1000);
  }
}

// function verificarSessaoPeriodicamente() {
//     setInterval(async () => {
//       try {
//         const response = await fetch(`/verificar_sessao?sessao_id=${sessao_id}`);
//         if (!response.ok) {
//           exibirToastDesconexao();
//           setTimeout(() => {
//             window.location.href = "/login";
//           }, 4000);
//         }
//       } catch (error) {
//         console.error("Erro ao verificar sessão:", error);
//         exibirToastDesconexao();
//         setTimeout(() => {
//           window.location.href = "/login";
//         }, 4000);
//       }
//     }, 2 * 60 * 1000); // verifica a cada 2 minutos
//   }
async function retryFetch(url, maxRetries = 3, initialDelay = 1000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
          const response = await fetch(url);
          if (response.status === 401) {
              const errorData = await response.json().catch(() => ({}));
              if (errorData.detail === "Sessão inválida ou expirada") {
                  throw new Error("Sessão inválida ou expirada");
              }
              throw new Error(`HTTP 401: ${errorData.detail || "Erro desconhecido"}`);
          }
          if (!response.ok) {
              throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          return await response.json();
      } catch (error) {
          if (error.message === "Sessão inválida ou expirada") {
              throw error; // Não retentar para sessão inválida
          }
          if (attempt === maxRetries) {
              throw error; // Esgotou tentativas
          }
          console.warn(`Tentativa ${attempt} falhou: ${error.message}. Retentando em ${initialDelay * attempt}ms...`);
          await new Promise(resolve => setTimeout(resolve, initialDelay * attempt));
      }
  }
}

function verificarSessaoPeriodicamente() {
  setInterval(async () => {
      try {
          const data = await retryFetch(`/check_session?sessao_id=${sessao_id}`);
          if (data.status !== "ok") {
              console.error("Sessão inválida: resposta inesperada", data);
              exibirToastDesconexao("Sessão inválida ou expirada");
              setTimeout(() => {
                  window.location.href = "/login";
              }, 4000);
          }
      } catch (error) {
          if (error.message === "Sessão inválida ou expirada") {
              console.error("Sessão expirada confirmada:", error.message);
              exibirToastDesconexao("Sessão inválida ou expirada");
              setTimeout(() => {
                  window.location.href = "/login";
              }, 4000);
          } else {
              console.error(`Erro ao verificar sessão (tentativas esgotadas): ${error.message}`);
              exibirToastDesconexao("Erro temporário, tentando novamente em 2 minutos...");
              // Não desconecta, espera próxima verificação
          }
      }
  }, 120000); // verifica a cada 2 minutos
}
function tratarMensagemWebSocket(data) {
  switch (data.type) {

    case "status_pacotes":
      if (data.status === "completed") {
        
        atualizarStatusBanner("Transcrição Finalizada! Pronto para gerar relatório.", "success");
        clearTimeout(tempoMaximoTimeout);
        stopPolling(8);

        const gerarBtn = document.getElementById('gerarRelatorioBtn');
        gerarBtn.disabled = false;
        gerarBtn.style.display = 'inline';

        document.getElementById('stopBtn').disabled = false;

      } else if (data.status === "pending") {
        // logMessage(data.message);
        
        setTimeout(() => verificarPacotesPendentes(), 5000);
      } else if (data.status === "error") {
        // logMessage(data.message);
      
      }
      break;

    case "ok":
      break;

    case "relatorio_status":
      if (data.status === "success") {
        esconderModalProgresso();
        atualizarStatusBanner("Pronto para realizar download.", "success");
        
        // logMessage(data.message);
        document.getElementById('gerarRelatorioBtn').disabled = true;
        document.getElementById('startBtn').style.display = 'none';
        document.getElementById('stopBtn').style.display = 'none';
      } else if (data.status === "error") {
        // logMessage(data.message);
      }
      break;

    case "relatorio_editavel":
      const relatorioArea = document.getElementById('relatorioArea');
      if (relatorioArea) {
        relatorioArea.value = data.relatorio;
      }
      break;

    case "transcription_update":
      const transcriptionArea = document.getElementById('transcriptionArea');
      if (transcriptionArea) {
        transcriptionArea.value += data.transcription + "\n";
        transcriptionArea.scrollTop = transcriptionArea.scrollHeight;
      }
      break;

    case "transcription_status":
        // logMessage(`Status da transcrição: ${data.status}`);
        break;

    case "baixar_relatorio_status":
        if (data.status === "success") {
            const btnDownload = document.getElementById('baixarRelatorioBtn');
            btnDownload.style.display = 'inline';
            btnDownload.disabled = false;
        } else {
            alert(data.message);
        }
        if (window._onDownloadReady) {
            window._onDownloadReady(data.status);
            window._onDownloadReady = null;
        }
        break;

    case "nova_consulta_status":
      if (data.status === "success") {
        alert("Sessao reiniciada com sucesso. Dados antigos foram removidos.");
        resetInterface();
      } else if (data.status === "error") {
        alert(`Erro ao reiniciar sessao: ${data.message}`);
      }
      break;

    case "log_frontend":
        // logMessage(`[BACKEND]: ${data.payload.mensagem}`);
        break;

    case "error":
      console.error("Erro recebido do backend:", data.message);
      break;

    default:
      console.warn("Tipo de evento desconhecido:", data.type);
  }
}


conectarWebSocket();
verificarSessaoPeriodicamente();  



// ========== Funções de Sessão e Logout ==========
document.addEventListener('DOMContentLoaded', () => {
    verificarSessao();
    configurarSelecaoProfissaoNecessidade();
    configurarLogout();
    verificarCampos();
});



function verificarSessao() {
    if (!sessao_id) {
        window.location.href = "/login";
    }
}


function configurarLogout() {
    document.getElementById("logoutBtn").onclick = () => {
        enviarWebSocket("logout", { sessao_id: sessao_id });
        localStorage.removeItem("sessao_id");
        window.location.href = "/login";
    };
}

// ##############Funções utilitárias para UI moderna:###########################  


function atualizarStatusBanner(mensagem, tipo = 'primary', duracao = 3000) {
  const banner = document.getElementById('statusBanner');
  banner.className = `alert alert-${tipo} d-flex align-items-center mt-3`;
  document.getElementById('statusMensagem').textContent = mensagem;
  banner.style.display = 'flex';

  // Limpa qualquer timer anterior, se houver
  if (statusBannerTimeout) {
    clearTimeout(statusBannerTimeout);
  }

  // Esconde o banner após a duração definida (padrão: 3 segundos)
  statusBannerTimeout = setTimeout(() => {
    banner.style.display = 'none';
  }, duracao);
}
  
  // function esconderStatusBanner() {
  //   const banner = document.getElementById('statusBanner');
  //   if (banner) banner.style.display = 'none';
  // }
  
  function mostrarModalProgresso() {
    new bootstrap.Modal(document.getElementById('modalProgresso')).show();
  }
  
  function esconderModalProgresso() {
    const modal = bootstrap.Modal.getInstance(document.getElementById('modalProgresso'));
    if (modal) modal.hide();
  }
// ========== Funcoes de Dados do Participante ==========

function gerarUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0,
            v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function verificarCampos() {
    document.querySelectorAll('#formDadosPaciente input').forEach(input => {
        input.addEventListener('input', validarFormulario);
    });
}

function validarFormulario() {
    const nome = document.getElementById('nome').value;
    document.getElementById('sendDataBtn').disabled = !(nome);
}


// ========== Funções de Profissão e Necessidade ==========
function configurarSelecaoProfissaoNecessidade() {
  const rawProfissao = localStorage.getItem('profissao');
  const normalize = (s) => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase();
  const profissaoNorm = normalize(rawProfissao);
  const PROFISSAO_MAP = {
    'medico': 'Médico',
    'psicologo': 'Psicólogo',
    'juiz': 'Juíz',
    'administrador': 'Administrador',
    'advogado': 'Advogado'
  };
  const profissao = PROFISSAO_MAP[profissaoNorm] || rawProfissao;

  const necessidadeSelect = document.getElementById('selecaoNecessidade');
  const startConsultaBtn = document.getElementById('startConsultaBtn');
  // let necessidade = "";

  const opcoesNecessidade = {

      "Administrador": [
          "Consulta Padrão",
          "Consulta de Oftalmologia",
          "Consulta de Neurologia",
          "Consulta de Neuropediatria",
          "Consulta de Cirurgia Plástica - Face",
          "Atestado",
          "Laudo",
          "Receita",
          "Exame",
          "Consulta Psicólogo",
          "Reunião", 
          "Depoimento", 
          "Audiência"
      ],
      "Médico": [
          "Consulta Padrão",
          "Consulta de Oftalmologia",
          "Consulta de Neurologia",
          "Consulta de Neuropediatria",
          "Consulta de Cirurgia Plástica - Face",
          "Atestado",
          "Laudo",
          "Receita",
          "Exame",
          "Reunião", 
          "Consulta de Dermatologia",
          "Exame de Colonoscopia",
          "Exame de Endoscopia Digestiva Alta",

      ],
      "Psicólogo": ["Consulta", "Atestado"],
      "Advogado": ["Depoimento", "Reunião"],
      "Juíz": ["Audiência"]
  };

  // Preenche o select de profissão e desabilita
  if (profissao) {
      document.getElementById('profissaoDisplay').textContent = profissao;

      // Popula necessidades conforme profissão
      necessidadeSelect.innerHTML = '<option value="" disabled selected>Selecione a finalidade</option>';
      if (opcoesNecessidade[profissao]) {
          necessidadeSelect.disabled = false;
          opcoesNecessidade[profissao].forEach(necessidadeOp => {
              const option = document.createElement('option');
              option.value = necessidadeOp;
              option.textContent = necessidadeOp;
              necessidadeSelect.appendChild(option);
          });
      } else {
          necessidadeSelect.disabled = true;
      }
  }

  // Listener para necessidade
  necessidadeSelect.addEventListener('change', () => {
      necessidade = necessidadeSelect.value;
      localStorage.setItem('necessidade', necessidade)
      console.log("Necessidade selecionada:", necessidade);
      validarSelecao();
  });

  function validarSelecao() {
      startConsultaBtn.disabled = !(profissao && necessidade);
  }

  startConsultaBtn.addEventListener('click', () => {
      // profissaoSelect.disabled = true;
      necessidadeSelect.disabled = true;
      startConsultaBtn.style.display = 'none';
      const transcricaoTab = new bootstrap.Tab(document.querySelector('#transcricao-tab'));
      transcricaoTab.show(); 
      document.getElementById('gravacaoHeader').style.display = 'block';
  });
}


function fetchTranscriptions() {
    if (!sessao_id || !patient_id || !necessidade) {  // Verifica se todos os parâmetros estão presentes
        console.error("Sessão ID, Patient ID ou necessidade não encontrados.");
        return;
    }

    // Monta a URL com os parâmetros de query string
    const url = `/transcriptions/${sessao_id}?patient_id=${encodeURIComponent(patient_id)}&necessidade=${encodeURIComponent(necessidade)}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            const transcription = data.transcription;  // Obtém a transcrição mais recente
            const transcriptionArea = document.getElementById('transcriptionArea');

            // Adiciona a nova transcrição ao final do texto existente
            if (typeof transcription === 'string') {
                transcriptionArea.value = transcription;
                transcriptionArea.scrollTop = transcriptionArea.scrollHeight;
            }
        })
        .catch(error => console.error("Erro ao buscar transcrição:", error));
}

// Inicie o polling usando a função fetchTranscriptions()
function startPolling() {
    // Prefer SSE stream; fallback to polling
    if (eventSource) {
        try { eventSource.close(); } catch (e) {}
        eventSource = null;
    }

    const transcriptionArea = document.getElementById(transcriptionArea);
    if (window.EventSource) {
        const url = `/transcriptions/stream/${sessao_id}?patient_id=${encodeURIComponent(patient_id)}&necessidade=${encodeURIComponent(necessidade)}`;
        eventSource = new EventSource(url);

        eventSource.addEventListener(transcription, (evt) => {
            const transcription = (evt.data || ).replace(/
/g, n);
            transcriptionArea.value = transcription;
            transcriptionArea.scrollTop = transcriptionArea.scrollHeight;
        });

        eventSource.addEventListener(error, () => {
            try { eventSource.close(); } catch (e) {}
            eventSource = null;
            if (pollingInterval) clearInterval(pollingInterval);
            pollingInterval = setInterval(fetchTranscriptions, 2000);
        });

        return;
    }

    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(fetchTranscriptions, 2000);
}


function stopPolling() {
    if (eventSource) {
        try { eventSource.close(); } catch (e) {}
        eventSource = null;
    }
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}



// Chama a função para validar o formulário sempre que um campo é alterado
document.querySelectorAll('#formDadosPaciente input').forEach(input => {
    input.oninput = validarFormulario;
});



function timeToString(time) {
    let diffInHrs = time / 3600000;
    let hh = Math.floor(diffInHrs);
    let diffInMin = (diffInHrs - hh) * 60;
    let mm = Math.floor(diffInMin);
    let diffInSec = (diffInMin - mm) * 60;
    let ss = Math.floor(diffInSec);
    return `${hh.toString().padStart(2, "0")}:${mm.toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`;
}
function startTimer() {
    startTime = Date.now() - elapsedTime;
    timerInterval = setInterval(() => {
        elapsedTime = Date.now() - startTime;
        document.getElementById("timer").innerHTML = timeToString(elapsedTime);
    }, 1000);
}

// Para o timer
function stopTimer() {
    clearInterval(timerInterval);
    }

// Reinicia o timer
function resetTimer() {
clearInterval(timerInterval);
document.getElementById("timer").innerHTML = "00:00:00";
elapsedTime = 0;
}

// Eventos de clique para os botões
document.getElementById("startBtn").addEventListener("click", startTimer);
// document.getElementById("stopBtn").addEventListener("click", stopTimer);
document.getElementById("novaConsultaBtn").addEventListener("click", resetTimer);
document.getElementById("baixarRelatorioBtn").addEventListener("click", resetTimer);



document.getElementById('sendDataBtn').onclick = () => {
  const nome = document.getElementById('nome').value;
  const endereco = document.getElementById('endereco').value || 'Não informado';
  const dataNascimento = document.getElementById('dataNascimento').value || 'Não informado';
  const cpf = document.getElementById('cpf').value || 'Não informado';
  patient_id = gerarUUID();

  const payload = {
      nome,
      endereco,
      dataNascimento,
      cpf,
      sessao_id: sessao_id,
      patient_id: patient_id,
  };

  // console.log("📤 Enviando dados do paciente via WebSocket:", payload);

  enviarWebSocket("dados_paciente", payload);

  // logMessage("Dados do paciente capturados com sucesso!");
  atualizarStatusBanner("Dados capturados com sucesso!", "success");
  document.querySelectorAll('#formDadosPaciente input').forEach(input => {
      input.disabled = true;
  });

  document.getElementById('sendDataBtn').style.display = 'none';
  // Habilita os controles da aba 2
  // document.getElementById('selecaoProfissao').disabled = false;
  document.getElementById('selecaoNecessidade').disabled = false;
  document.getElementById('startConsultaBtn').disabled = true;
  // Ativa a aba Consulta
  const abaConsultaBtn = document.getElementById('consulta-tab');
  if (abaConsultaBtn) {
      // Força a tab a ser ativada usando Bootstrap
      const aba = new bootstrap.Tab(abaConsultaBtn);
      aba.show();

      // Fallback: também simula clique
      setTimeout(() => abaConsultaBtn.click(), 100);
  } else {
      console.error("Botao da aba Sessao nao encontrado!");
  }
};

// Adicione um event listener para o botão "Iniciar Consulta"
document.getElementById('startConsultaBtn').onclick = () => {
 
    atualizarStatusBanner("Pronto para iniciar a gravação!", "success");

    // Deixar as seleções de profissão e necessidade inalteráveis

    // document.getElementById('selecaoProfissao').disabled = true;
    document.getElementById('selecaoNecessidade').disabled = true;
    // Exibe a seção de gravação e oculta a seção de seleção de profissão e necessidade
    document.getElementById('gravacaoHeader').style.display = 'block';
    // Habilita os botões de gravação e ocultar o botão de "Iniciar Consulta"
    document.getElementById('startBtn').style.display = 'inline';
    document.getElementById('stopBtn').style.display = 'inline';
    document.getElementById('startConsultaBtn').style.display = 'none';
};


let stream = null;
let mediaRecorderA = null;
let mediaRecorderB = null;
let chunksA = [];
let chunksB = [];
let gravandoA = false;
let gravandoB = false;
let wakeLock = null;

async function ativarWakeLock() {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      console.log("Wake Lock ativado.");
      
      // Reativa se for liberado por algum motivo (ex: mudança de foco)
      wakeLock.addEventListener('release', () => {
        console.warn("Wake Lock liberado. Tentando reativar...");
        ativarWakeLock();
      });
    } else {
      console.warn("Wake Lock API não suportada neste navegador.");
    }
  } catch (err) {
    console.error(`Erro ao ativar Wake Lock: ${err.name}, ${err.message}`);
  }
}

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      ativarWakeLock(); // Mantém a tela ligada
    } else {
      showToast("⚠️ Celulares e tablets param a transcrição ao sair do navegador!", "warning");
    }
  });
// let scheduleAStopTimeout, scheduleBStartTimeout, scheduleBStopTimeout;
// let isRecording = false;

// Inicia a gravação
document.getElementById("startBtn").addEventListener("click", async () => {
    ativarWakeLock()
    document.getElementById('gravacaoHeader').style.display = 'block';
    enviarWebSocket("start_gravacao", {
        sessao_id: sessao_id,
        patient_id: patient_id,
        necessidade: necessidade
    });   

    if (!isRecording) {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            mediaRecorderA = new MediaRecorder(stream);
            mediaRecorderB = new MediaRecorder(stream);

            mediaRecorderA.ondataavailable = e => chunksA.push(e.data);
            mediaRecorderB.ondataavailable = e => chunksB.push(e.data);

            mediaRecorderA.onstop = () => processarBlob(chunksA, 'A');
            mediaRecorderB.onstop = () => processarBlob(chunksB, 'B');

            startPingPongCycle();

            isRecording = true;
            startPolling();

       
            
            atualizarStatusBanner("Gravando áudio... Enviando pacotes", "info");
        } catch (error) {
            console.error("Erro ao acessar microfone:", error);
            
        }
    } else {
        
    }
});

document.getElementById("stopBtn").addEventListener("click", pararGravacao);

function pararGravacao() {
    const stopBtn = document.getElementById("stopBtn");
    // ⚠️ Cancelar todos os timers logo no início
    clearTimeout(scheduleAStopTimeout);
    clearTimeout(scheduleBStartTimeout);
    clearTimeout(scheduleBStopTimeout);

    // ⚠️ Parar gravadores imediatamente
    if (mediaRecorderA && mediaRecorderA.state !== "inactive") mediaRecorderA.stop();
    if (mediaRecorderB && mediaRecorderB.state !== "inactive") mediaRecorderB.stop();
    // Bloquear clique duplo
    stopBtn.disabled = true;
    stopTimer();
    const duracaoSessaoParcial = timeToString(elapsedTime);
    if (elapsedTime < 8000) {
        
        atualizarStatusBanner("Você precisa gravar pelo menos um trecho antes de gerar o relatório.", "warning");

        

    
        // Resetar gravação e reabilitar botão
        isRecording = false;
        // document.getElementById('novaConsultaBtn').style.display = 'inline';
        // document.getElementById('novaConsultaBtn').disabled = false;
        
        stopBtn.disabled = false;
        stopPolling(8);
        setTimeout(() => {
            const modal = new bootstrap.Modal(document.getElementById('modalContinuarGravacao'));
            modal.show();
          
            // Sim: só fecha o modal, segue na mesma aba
            document.getElementById('btnSimContinuarGravacao').onclick = () => {
              modal.hide();
            };
          
            // Não: troca para aba Consulta e dispara nova consulta
            document.getElementById('btnNaoContinuarGravacao').onclick = () => {
              modal.hide();
              new bootstrap.Tab(document.querySelector('#consulta-tab')).show();
              setTimeout(() => {
                document.getElementById('novaConsultaBtn').click();
              }, 200);
            };
          }, 800);
        return; // Encerra aqui e não permite gerar relatório
    }
    enviarWebSocket("parar_gravacao", {
        sessao_id: sessao_id,
        patient_id: patient_id,
        necessidade: necessidade,
        duracao_transcricao_parcial: duracaoSessaoParcial
    });

    if (isRecording) {
        // clearTimeout(scheduleAStopTimeout);
        // clearTimeout(scheduleBStartTimeout);
        // clearTimeout(scheduleBStopTimeout);

        // if (mediaRecorderA && mediaRecorderA.state !== "inactive") mediaRecorderA.stop();
        // if (mediaRecorderB && mediaRecorderB.state !== "inactive") mediaRecorderB.stop();

        isRecording = false;
        // logMessage("Gravação parada. Verificando pacotes pendentes...");
        atualizarStatusBanner("Verificando transcrições pendentes...", "warning");
        stopPolling(8);
        tempoMaximoTimeout = setTimeout(() => {
            // logMessage("Tempo máximo atingido. Liberando botão de relatório.");

            stopPolling(8);

            gerarRelatorioBtn.style.display = 'inline';
            gerarRelatorioBtn.disabled = false;

            // Reabilita botão de gravação
            stopBtn.disabled = false;
        }, 18000);
        verificarPacotesPendentes();
        // document.getElementById('gerarRelatorioBtn').style.display = 'inline-block';
    } else {
        atualizarStatusBanner("Nenhuma gravação está em andamento.");
    }
}

// Ciclo ping-pong usando MediaRecorder
function startPingPongCycle() {
    chunksA = [];
    mediaRecorderA.start();
    gravandoA = true;
    // logMessage("mediaRecorderA gravando agora (t=0s)");

    scheduleAStopTimeout = setTimeout(() => {
        if (gravandoA) {
            mediaRecorderA.stop();
            gravandoA = false;
        }
    }, CHUNK_DURATION_SEC * 1000);

    scheduleBStartTimeout = setTimeout(() => {
        chunksB = [];
        mediaRecorderB.start();
        gravandoB = true;
        // logMessage("mediaRecorderB gravando (t=7s, sobreposição de 1s)");
    }, RECORD_B_START_SEC * 1000);

    scheduleBStopTimeout = setTimeout(() => {
        if (gravandoB) {
            mediaRecorderB.stop();
            gravandoB = false;
        }
        if (isRecording) {
            startPingPongCycle();
        }
    }, (RECORD_B_START_SEC + CHUNK_DURATION_SEC) * 1000);
}

// Processa e envia o blob via WebSocket
function processarBlob(chunks, nome) {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    // console.log(`[${nome}] Tamanho do blob gerado: ${blob.size} bytes`);

    const reader = new FileReader();
    reader.onloadend = () => {
        const base64Audio = reader.result.split(',')[1];
        const pacote_id = Date.now();

        enviarWebSocket("audio_chunk", {
            audioData: base64Audio,
            pacote_id,
            sessao_id,
            patient_id,
            necessidade
        });

        // logMessage(`Enviado chunk (recorder=${nome}), pacote_id=${pacote_id}`);
    };
    reader.readAsDataURL(blob);
}

// ========== Função para verificar pacotes pendentes ==========

function verificarPacotesPendentes() {
    if (!sessao_id || !patient_id || !necessidade) {
        // logMessage("Sessão ID, Patient ID ou Necessidade não encontrados.");
        return;
    }

    enviarWebSocket("verificar_pacotes_pendentes", {
        sessao_id,
        patient_id,
        necessidade
    });
}



// ========== Geração de relatório ==========

document.getElementById('gerarRelatorioBtn').addEventListener("click", () => {
    const duracaoSessao = timeToString(elapsedTime);
    const btn = document.getElementById('gerarRelatorioBtn');

    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-file-earmark-text"></i> Gerar Relatorio...';
    
    document.getElementById('baixarRelatorioBtn').style.display = 'inline';
    document.getElementById('startBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = 'none';
    mostrarModalProgresso();
    enviarWebSocket("gerar_relatorio", {
        duracaoConsulta: duracaoSessao,
        sessao_id,
        profissao,
        necessidade,
        patient_id
    });

    const relatorioTab = new bootstrap.Tab(document.querySelector('#relatorio-tab'));
    relatorioTab.show();
});

// ========== Baixar relatório ==========

document.getElementById('baixarRelatorioBtn').addEventListener("click", async () => {
    const relatorioEditado = document.getElementById('relatorioArea').value;
    
    atualizarStatusBanner("Preparando relatório para download...", "info");

    const downloadReady = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error("Timeout")), 15000);
        window._onDownloadReady = (status) => {
            clearTimeout(timeout);
            if (status === "success") resolve();
            else reject(new Error("Erro ao salvar relatório"));
        };
    });

    enviarWebSocket("preparar_relatorio", {
        relatorio_editado: relatorioEditado,
        sessao_id,
        patient_id,
        necessidade
    });

    try {
        await downloadReady;

        const response = await fetch(`/download_relatorio?sessao_id=${sessao_id}&patient_id=${patient_id}&necessidade=${necessidade}`);
        if (!response.ok) {
            alert("Erro ao baixar relatório. Tente novamente.");
            return;
        }
        
        const contentDisposition = response.headers.get('Content-Disposition');
        let suggestedFilename = "Relatorio.docx";
        if (contentDisposition && contentDisposition.includes("filename=")) {
            let filenamePart = contentDisposition.split("filename=")[1];
            filenamePart = filenamePart.trim().replace(/['"]/g, "");
            suggestedFilename = filenamePart;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = suggestedFilename;
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        atualizarStatusBanner("Download concluído.", "success");
    } catch (error) {
        console.error("Erro ao salvar relatório no backend:", error);
        if (error.message === "Timeout") {
            alert("O servidor demorou muito para preparar o relatório. Tente novamente.");
        } else {
            alert("Erro ao salvar relatório. Tente novamente.");
        }
        atualizarStatusBanner("Erro no download. Tente novamente.", "danger");
    }
    // Permite nova seleção de necessidade
    const necessidadeSelect = document.getElementById('selecaoNecessidade');
    necessidadeSelect.value = '';  // Reseta a seleção para "Selecione a necessidade"
    necessidadeSelect.disabled = false;  // Habilita a seleção para uma nova necessidade

    document.getElementById('startConsultaBtn').style.display = 'inline';
    document.getElementById('startConsultaBtn').disabled = false;

    document.getElementById('novaConsultaBtn').style.display = 'inline';
    document.getElementById('novaConsultaBtn').disabled = false;

    document.getElementById('gerarRelatorioBtn').style.display = 'none';
    document.getElementById('baixarRelatorioBtn').style.display = 'none';

    document.getElementById('transcriptionArea').value = '';
    document.getElementById('relatorioArea').value = '';
    // document.getElementById('logArea').value = '';
    setTimeout(() => {
        const modal = new bootstrap.Modal(document.getElementById('modalNovaTranscricao'));
        modal.show();
      
        document.getElementById('btnSimNovaTranscricao').onclick = () => {
          modal.hide();
          new bootstrap.Tab(document.querySelector('#consulta-tab')).show();
        };
      
        document.getElementById('btnNaoNovaTranscricao').onclick = () => {
          modal.hide();
          document.getElementById('novaConsultaBtn').click();
        };
    }, 800);
    // const pacienteTab = new bootstrap.Tab(document.querySelector('#dados-tab'));
    // pacienteTab.show();
});


document.getElementById('novaConsultaBtn').addEventListener("click", () => {
    enviarWebSocket("nova_consulta", { sessao_id });
    atualizarStatusBanner("Nova consulta iniciada com sucesso.", "success");
  });

function resetInterface() {
    document.querySelectorAll('#formDadosPaciente input').forEach(input => {
        input.value = '';
        input.disabled = false;
    });

    document.getElementById('sendDataBtn').style.display = 'inline';
    document.getElementById('sendDataBtn').disabled = true;

    // const profissaoSelect = document.getElementById('selecaoProfissao');
    // profissaoSelect.value = '';
    // profissaoSelect.disabled = false;

    const necessidadeSelect = document.getElementById('selecaoNecessidade');
    necessidadeSelect.innerHTML = '<option value="" disabled selected>Selecione a necessidade</option>';

    // document.getElementById('selecaoProfissao').disabled = true;

    const startConsultaBtn = document.getElementById('startConsultaBtn');
    startConsultaBtn.style.display = 'inline';
    startConsultaBtn.disabled = true;

    document.getElementById('novaConsultaBtn').style.display = 'none';
    document.getElementById('gerarRelatorioBtn').style.display = 'none';

    document.getElementById('transcriptionArea').value = '';
    document.getElementById('relatorioArea').value = '';
    // document.getElementById('logArea').value = '';
    // const pacienteTab = new bootstrap.Tab(document.querySelector('#dados-tab'));
    // pacienteTab.show();
}




// --- Código para Teste de Microfone Integrado ---

document.addEventListener('DOMContentLoaded', () => {
    const startMicTestButton = document.getElementById('start-mic-test');
    const stopMicTestButton = document.getElementById('stop-mic-test');
    const audioLevel = document.getElementById('audio-level');
    const statusDisplay = document.getElementById('status');
    const micTestPanel = document.getElementById('micTestPanel');
    const micToggleBtn = document.getElementById('toggleMicTest');
    const tabButtons = document.querySelectorAll('#tabs .nav-link');

    let mediaStreamMicTest = null;
    let animationIdMicTest = null;
    let audioContextMicTest = null;
    let analyserMicTest = null;
    let dataArrayMicTest = null;

    // ========== Toggle de Exibição ==========
    micToggleBtn?.addEventListener('click', () => {
        const activeTab = document.querySelector('.nav-tabs .nav-link.active');
        if (activeTab && activeTab.id === 'dados-tab') {
            micTestPanel.style.display = micTestPanel.style.display === 'none' ? 'block' : 'none';
        } else {
            alert("O teste de microfone só está disponível na aba 'Paciente'.");
        }
    });

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            micTestPanel.style.display = 'none';
        });
    });

    // ========== Lógica do Teste de Microfone ==========

    if (!startMicTestButton || !stopMicTestButton || !audioLevel || !statusDisplay) return;

    async function listarDispositivos() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioDevices = devices.filter(device => device.kind === 'audioinput');

            const selectMic = document.getElementById('select-mic');
            if (!selectMic) return;

            if (audioDevices.length === 0) {
                selectMic.innerHTML = '<option value="" disabled selected>Nenhum microfone encontrado</option>';
                startMicTestButton.disabled = true;
                return;
            }

            selectMic.innerHTML = '<option value="" disabled selected>Selecione o microfone</option>';
            audioDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.deviceId;
                option.text = device.label || `Microfone ${device.deviceId}`;
                selectMic.appendChild(option);
            });

        } catch (error) {
            console.error('Erro ao listar dispositivos:', error);
            statusDisplay.textContent = 'Erro ao listar dispositivos de áudio.';
            startMicTestButton.disabled = true;
        }
    }

    async function startMicTest() {
        statusDisplay.textContent = '';
        const selectMic = document.getElementById('select-mic');
        const selectedDeviceId = selectMic?.value;
        if (!selectedDeviceId) {
            statusDisplay.textContent = 'Por favor, selecione um microfone.';
            return;
        }

        try {
            mediaStreamMicTest = await navigator.mediaDevices.getUserMedia({
                audio: { deviceId: { exact: selectedDeviceId } }
            });

            audioContextMicTest = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContextMicTest.createMediaStreamSource(mediaStreamMicTest);
            analyserMicTest = audioContextMicTest.createAnalyser();
            analyserMicTest.fftSize = 256;
            const bufferLength = analyserMicTest.frequencyBinCount;
            dataArrayMicTest = new Uint8Array(bufferLength);
            source.connect(analyserMicTest);

            updateAudioLevelMicTest();

            startMicTestButton.disabled = true;
            stopMicTestButton.disabled = false;

            // logMessage?.('Teste de microfone iniciado.');

        } catch (error) {
            console.error('Erro ao acessar o microfone:', error);
            if (error.name === 'NotAllowedError') {
                statusDisplay.textContent = 'Permissão para acessar o microfone foi negada.';
            } else if (error.name === 'NotFoundError') {
                statusDisplay.textContent = 'Nenhum microfone encontrado. Por favor, conecte um microfone e tente novamente.';
            } else {
                statusDisplay.textContent = 'Erro ao acessar o microfone. Tente novamente.';
            }
            // logMessage?.('Erro ao iniciar o teste de microfone.');
        }
    }

    function stopMicTest() {
        if (animationIdMicTest) cancelAnimationFrame(animationIdMicTest);
        if (audioContextMicTest) audioContextMicTest.close();
        if (mediaStreamMicTest) {
            mediaStreamMicTest.getTracks().forEach(track => track.stop());
        }

        audioLevel.style.width = '0%';
        statusDisplay.textContent = '';
        statusDisplay.style.color = 'red';

        startMicTestButton.disabled = false;
        stopMicTestButton.disabled = true;
        micTestPanel.style.display = 'none';
        // logMessage?.('Teste de microfone parado.');
    }

    function updateAudioLevelMicTest() {
        analyserMicTest.getByteFrequencyData(dataArrayMicTest);
        let sum = 0;
        for (let i = 0; i < dataArrayMicTest.length; i++) sum += dataArrayMicTest[i];
        const average = sum / dataArrayMicTest.length;
        const percentage = Math.min(100, (average / 255) * 100);
        audioLevel.style.width = `${percentage}%`;

        if (percentage < 10) {
            statusDisplay.textContent = 'Nível de áudio muito baixo. Tente falar mais alto.';
            statusDisplay.style.color = 'orange';
        } else if (percentage > 90) {
            statusDisplay.textContent = 'Nível de áudio muito alto. Tente diminuir o volume.';
            statusDisplay.style.color = 'orange';
        } else {
            statusDisplay.textContent = 'Nível de áudio adequado.';
            statusDisplay.style.color = 'green';
        }

        animationIdMicTest = requestAnimationFrame(updateAudioLevelMicTest);
    }

    startMicTestButton.addEventListener('click', startMicTest);
    stopMicTestButton.addEventListener('click', stopMicTest);

    async function initializeMicrophoneTest() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            await listarDispositivos();
        } catch (error) {
            console.error('Erro ao obter permissão inicial para microfone:', error);
            statusDisplay.textContent = 'Permissão para acessar o microfone foi negada.';
            startMicTestButton.disabled = true;
        }
    }

    initializeMicrophoneTest();
});