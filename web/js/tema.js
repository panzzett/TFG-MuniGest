/* ======================================================================
   Trabajo Fin de Grado en Ingenieria Informatica
   Universidad Internacional de La Rioja (UNIR)
   Prototipo de software de tramitacion de expedientes electronicos
   para administraciones locales
   Autor: Carlos Galvez Reguera
   Ano: 2026

   Este archivo forma parte de este proyecto, desarrollado como
   Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.

   Licencia: MIT
   ====================================================================== */

/* Selector de tema (claro / oscuro / sistema) con persistencia en localStorage. */
window.Tema = (function () {
  const CLAVE = 'tema';
  const VALIDOS = ['sistema', 'claro', 'oscuro'];
  const ETQ = { sistema: 'Sistema', claro: 'Claro', oscuro: 'Oscuro' };

  function leer() {
    const v = (localStorage.getItem(CLAVE) || '').toLowerCase();
    return VALIDOS.includes(v) ? v : 'sistema';
  }

  function aplicar(valor) {
    const v = VALIDOS.includes(valor) ? valor : 'sistema';
    if (v === 'sistema') document.documentElement.removeAttribute('data-tema');
    else document.documentElement.setAttribute('data-tema', v);
    localStorage.setItem(CLAVE, v);
    actualizarBoton(v);
    document.dispatchEvent(new CustomEvent('temaCambiado', { detail: { tema: v } }));
  }

  function actualizarBoton(v) {
    const btn = document.getElementById('btn-tema');
    const etq = document.getElementById('tema-etq');
    if (btn) btn.dataset.temaActual = v;
    if (etq) etq.textContent = ETQ[v] || ETQ.sistema;
    document.querySelectorAll('[data-tema-opcion]').forEach(op => {
      op.setAttribute('aria-checked', op.dataset.temaOpcion === v ? 'true' : 'false');
    });
  }

  function activar() {
    const btn = document.getElementById('btn-tema');
    const menu = document.getElementById('menu-tema');
    if (!btn || !menu) return;

    actualizarBoton(leer());

    const opciones = Array.from(menu.querySelectorAll('[data-tema-opcion]'));

    function abrir() {
      menu.classList.remove('oculto');
      btn.setAttribute('aria-expanded', 'true');
      const sel = opciones.find(o => o.getAttribute('aria-checked') === 'true') || opciones[0];
      if (sel) sel.focus();
    }
    function cerrar(devolverFoco) {
      menu.classList.add('oculto');
      btn.setAttribute('aria-expanded', 'false');
      if (devolverFoco) btn.focus();
    }

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const abierto = btn.getAttribute('aria-expanded') === 'true';
      abierto ? cerrar(false) : abrir();
    });

    btn.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        abrir();
      }
    });

    opciones.forEach((op, i) => {
      op.addEventListener('click', () => {
        aplicar(op.dataset.temaOpcion);
        cerrar(true);
      });
      op.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          opciones[(i + 1) % opciones.length].focus();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          opciones[(i - 1 + opciones.length) % opciones.length].focus();
        } else if (e.key === 'Home') {
          e.preventDefault(); opciones[0].focus();
        } else if (e.key === 'End') {
          e.preventDefault(); opciones[opciones.length - 1].focus();
        } else if (e.key === 'Escape') {
          e.preventDefault(); cerrar(true);
        } else if (e.key === 'Tab') {
          cerrar(false);
        }
      });
    });

    document.addEventListener('click', (e) => {
      if (btn.getAttribute('aria-expanded') !== 'true') return;
      if (!menu.contains(e.target) && e.target !== btn) cerrar(false);
    });
  }

  return { leer, aplicar, activar };
})();
