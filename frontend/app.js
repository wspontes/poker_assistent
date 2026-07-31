"use strict";

const $ = (id) => document.getElementById(id);

const elFotoInput = $("fotoInput");
const elBtnTirarFoto = $("btnTirarFoto");
const elBtnEscolherFoto = $("btnEscolherFoto");
const elBtnEnviar = $("btnEnviar");
const elBtnTirarOutra = $("btnTirarOutra");
const elBtnNovaFoto = $("btnNovaFoto");
const elMotor = $("motorSelect");
const elDebug = $("debugToggle");
const elPreviewImg = $("previewImg");
const elResultImg = $("resultImg");
const elEtapaFoto = $("etapaFoto");
const elEtapaPreview = $("etapaPreview");
const elEtapaResultado = $("etapaResultado");
const elCarregando = $("carregando");
const elErro = $("erroBox");
const elConteudo = $("resultadoConteudo");
const elGridDebug = $("gridDebug");
const elJsonSaida = $("jsonSaida");
const elResumoMesa = $("resumoMesa");
const elResumoJogadores = $("resumoJogadores");
const elResumoObs = $("resumoObs");
const elJsonRaw = $("jsonRaw");
const elAcao = $("acaoSugerida");
const elStatusServidor = $("statusServidor");

let fotoSelecionada = null;

const NAIPES = { h: "♥", d: "♦", c: "♣", s: "♠" };

function simboloNaipe(s) {
  return NAIPES[s] || s;
}

function ehVermelha(carta) {
  return typeof carta === "string" && carta.length === 2 && "hd".includes(carta[1]);
}

function renderCarta(carta) {
  if (!carta) return "";
  const span = document.createElement("span");
  span.className = "carta" + (ehVermelha(carta) ? " vermelha" : "");
  const valor = carta[0].toUpperCase() === "T" ? "10" : carta[0].toUpperCase();
  span.textContent = valor + simboloNaipe(carta[1]);
  return span.outerHTML;
}

function renderCartas(cartas) {
  const box = document.createElement("div");
  box.className = "cartas-linha";
  if (Array.isArray(cartas) && cartas.length) {
    cartas.forEach((c) => (box.innerHTML += renderCarta(c)));
  } else {
    const vazia = document.createElement("span");
    vazia.className = "carta buraco";
    vazia.textContent = "?";
    box.appendChild(vazia);
  }
  return box;
}

function formatarNumero(valor) {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor !== "number") return String(valor);
  return valor.toLocaleString("pt-BR");
}

function esc(v) {
  if (v === null || v === undefined) return "";
  const div = document.createElement("div");
  div.textContent = String(v);
  return div.innerHTML;
}

function statusAtivo(ativo) {
  if (ativo === null || ativo === undefined) {
    return '<span class="status-ativo indefinido">Indefinido</span>';
  }
  return ativo
    ? '<span class="status-ativo ativo">Ativo</span>'
    : '<span class="status-ativo fold">Fold</span>';
}

function badgePosicao(posicao, principal) {
  const cls = principal ? " principal" : posicao ? "" : " desconhecida";
  return `<span class="badge-posicao${cls}">${esc(posicao) || "?"}</span>`;
}

/* ---------- Navegação entre etapas ---------- */

function mostrarEtapa(nome) {
  elEtapaFoto.classList.toggle("oculto", nome !== "foto");
  elEtapaPreview.classList.toggle("oculto", nome !== "preview");
  elEtapaResultado.classList.toggle("oculto", nome !== "resultado");
}

function abrirCamera() {
  elFotoInput.click();
}

elBtnTirarFoto.addEventListener("click", abrirCamera);
elBtnEscolherFoto.addEventListener("click", abrirCamera);
elBtnTirarOutra.addEventListener("click", () => {
  fotoSelecionada = null;
  elFotoInput.value = "";
  mostrarEtapa("foto");
});
elBtnNovaFoto.addEventListener("click", () => {
  fotoSelecionada = null;
  elFotoInput.value = "";
  mostrarEtapa("foto");
});

elFotoInput.addEventListener("change", (e) => {
  const arquivo = e.target.files && e.target.files[0];
  if (!arquivo) return;
  fotoSelecionada = arquivo;
  elPreviewImg.src = URL.createObjectURL(arquivo);
  mostrarEtapa("preview");
});

/* ---------- Envio ---------- */

elBtnEnviar.addEventListener("click", async () => {
  if (!fotoSelecionada) return;

  const motor = elMotor.value === "auto" ? "" : elMotor.value;
  const debug = elDebug.checked;

  elErro.classList.add("oculto");
  elConteudo.classList.add("oculto");
  elCarregando.classList.remove("oculto");
  elBtnEnviar.disabled = true;
  elBtnEnviar.textContent = "Analisando...";
  mostrarEtapa("resultado");

  try {
    const form = new FormData();
    form.append("arquivo", fotoSelecionada, fotoSelecionada.name || "foto.jpg");

    const url = `/api/reconhecer?debug=${debug}` + (motor ? `&motor=${encodeURIComponent(motor)}` : "");
    const resp = await fetch(url, { method: "POST", body: form });

    let dados;
    try {
      dados = await resp.json();
    } catch {
      throw new Error("Resposta do servidor não é JSON válido.");
    }

    if (!resp.ok) {
      const det = dados && dados.detail ? JSON.stringify(dados.detail) : resp.statusText;
      throw new Error(`Erro ${resp.status}: ${det}`);
    }

    renderResultado(dados);
  } catch (err) {
    elErro.textContent = "Falha ao enviar: " + err.message;
    elErro.classList.remove("oculto");
  } finally {
    elCarregando.classList.add("oculto");
    elBtnEnviar.disabled = false;
    elBtnEnviar.textContent = "Enviar para análise";
  }
});

/* ---------- Sugestão de ação ---------- */

function rotuloAcao(acao) {
  const rotulos = {
    raise: "Aumentar",
    bet: "Apostar",
    call: "Pagar",
    fold: "Desistir",
    check: "Passar",
    sem_acao: "Sem ação",
    sem_informacao: "Sem dados",
  };
  return rotulos[acao] || acao;
}

function renderAcao(dados) {
  const acao = dados.acao_sugerida;
  if (!acao) return;
  const detalhes = [
    acao.forca_mao ? `mão: ${acao.forca_mao}` : "",
    acao.equity_estimada !== undefined && acao.equity_estimada !== null
      ? `equity ~${(acao.equity_estimada * 100).toFixed(0)}%`
      : "",
    acao.pot_odds ? `pot odds ${(acao.pot_odds * 100).toFixed(0)}%` : "",
  ].filter(Boolean).join(" · ");

  elAcao.innerHTML = `
    <div class="acao-box acao-${esc(acao.acao)}">
      <div class="label">Sugestão de ação</div>
      <div class="acao-principal">${rotuloAcao(acao.acao)}${acao.valor ? ` ${formatarNumero(acao.valor)}` : ""}</div>
      ${detalhes ? `<div class="detalhes">${esc(detalhes)}</div>` : ""}
      <div class="motivo">${esc(acao.motivo)}</div>
    </div>`;
}

/* ---------- Renderização do resultado ---------- */

function renderResultado(dados) {
  elResultImg.src = elPreviewImg.src;
  renderAcao(dados);

  const mesa = dados.mesa || {};
  const blinds = (mesa.blinds || {});

  const metaMotor = [
    dados.motor_usado ? `motor: ${dados.motor_usado}` : "",
    dados.tempo_ms !== undefined ? `${dados.tempo_ms} ms` : "",
    dados.nota_fallback ? `aviso: ${dados.nota_fallback}` : "",
  ].filter(Boolean).join(" · ");

  let mesaHtml = '<div class="bloco-resumo"><h3>Mesa</h3>';
  mesaHtml += `<div class="chips-blinds">
      <span class="chip">SB <b>${formatarNumero(blinds.small_blind)}</b></span>
      <span class="chip">BB <b>${formatarNumero(blinds.big_blind)}</b></span>
    </div>`;
  mesaHtml += `<div class="pote">Pote: <b>${formatarNumero(mesa.pote)}</b></div>`;
  if (mesa.cartas_comunitarias && mesa.cartas_comunitarias.length) {
    mesaHtml += '<div class="pote">Comunitárias:</div>';
    mesaHtml += '<div class="cartas-linha">' + mesa.cartas_comunitarias.map(renderCarta).join("") + "</div>";
  }
  mesaHtml += "</div>";
  elResumoMesa.innerHTML = mesaHtml;

  let jogHtml = '<div class="bloco-resumo"><h3>Jogadores</h3>';
  const jogadores = Array.isArray(dados.jogadores) ? dados.jogadores : [];
  if (!jogadores.length) {
    jogHtml += '<p class="meta-jogador">Nenhum jogador reconhecido.</p>';
  }
  jogadores.forEach((j, i) => {
    const principal = j.eh_jogador_principal;
    jogHtml += `
      <div class="jogador">
        ${badgePosicao(j.posicao, principal)}
        <div class="infos-jogador">
          <div class="nome-jogador">
            ${esc(j.nome) || "<em>Nome não lido</em>"}
            ${principal ? '<span class="marca-voce">Você</span>' : ""}
          </div>
          <div class="meta-jogador">
            Stack: <b>${formatarNumero(j.stack)}</b>
            ${j.aposta_atual ? ` · Aposta: <span class="aposta">${formatarNumero(j.aposta_atual)}</span>` : ""}
            ${j.confianca ? ` · <span class="confianca">confiança: ${esc(j.confianca)}</span>` : ""}
          </div>
          <div class="cartas-linha" style="margin-top:0.4rem;">
            ${renderCartas(j.cartas).innerHTML}
          </div>
        </div>
        ${statusAtivo(j.ativo)}
      </div>`;
  });
  jogHtml += "</div>";
  elResumoJogadores.innerHTML = jogHtml;

  const obs = dados.observacoes;
  if (obs) {
    elResumoObs.innerHTML =
      '<div class="bloco-resumo"><h3>Observações</h3>' +
      '<div class="observacoes">' +
      esc(obs) +
      (metaMotor ? `\n\n<span class="confianca">${esc(metaMotor)}</span>` : "") +
      "</div></div>";
  } else if (metaMotor) {
    elResumoObs.innerHTML =
      '<div class="bloco-resumo"><h3>Meta</h3><div class="observacoes">' +
      esc(metaMotor) +
      "</div></div>";
  } else {
    elResumoObs.innerHTML = "";
  }

  elJsonRaw.textContent = JSON.stringify(dados, null, 2);
  elJsonSaida.textContent = JSON.stringify(dados, null, 2);
  elGridDebug.classList.toggle("oculto", !elDebug.checked);

  elCarregando.classList.add("oculto");
  elConteudo.classList.remove("oculto");
}

/* ---------- PWA ---------- */

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

let eventoInstalar = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  eventoInstalar = e;
  $("btnInstalar").classList.remove("oculto");
});

$("btnInstalar").addEventListener("click", async () => {
  if (!eventoInstalar) return;
  eventoInstalar.prompt();
  const escolha = await eventoInstalar.userChoice;
  if (escolha.outcome === "accepted") {
    $("btnInstalar").classList.add("oculto");
  }
  eventoInstalar = null;
});

/* ---------- Verificação do servidor ---------- */

(async function checarServidor() {
  try {
    const resp = await fetch("/api/health");
    const dados = await resp.json();
    elStatusServidor.textContent = `Servidor OK · motor padrão: ${dados.motor_padrao} · disponíveis: ${dados.motores_disponiveis.join(", ")}`;
    elStatusServidor.parentElement.classList.add("ok");
  } catch {
    elStatusServidor.textContent = "Servidor não acessível.";
    elStatusServidor.parentElement.classList.add("erro");
  }
})();
