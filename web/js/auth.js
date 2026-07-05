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

window.Auth = (function () {
  let usuarioActual = null;

  async function comprobarSesion() {
    try {
      const r = await U.api('GET', '/api/me');
      if (r && r.autenticado) { usuarioActual = r.usuario; return r.usuario; }
    } catch (e) {}
    usuarioActual = null;
    return null;
  }

  async function login(usuario, password) {
    const r = await U.api('POST', '/api/login', { json: { usuario, password } });
    usuarioActual = r.usuario;
    return r;
  }

  async function registro(usuario, password) {
    return U.api('POST', '/api/registro', { json: { usuario, password } });
  }

  async function logout() {
    try { await U.api('POST', '/api/logout'); } catch (e) {}
    usuarioActual = null;
  }

  function usuario() { return usuarioActual; }

  function pintarLogin(contenedor, alLoguear) {
    U.montarPlantilla('tpl-login', contenedor);
    if (window.Tema) Tema.activar();

    const tabs = contenedor.querySelectorAll('[role=tab]');
    const fLog = contenedor.querySelector('#form-login');
    const fReg = contenedor.querySelector('#form-registro');

    function activar(nombre) {
      tabs.forEach(t => {
        const sel = t.dataset.tab === nombre;
        t.setAttribute('aria-selected', sel ? 'true' : 'false');
        t.tabIndex = sel ? 0 : -1;
      });
      fLog.classList.toggle('oculto', nombre !== 'login');
      fReg.classList.toggle('oculto', nombre !== 'registro');
      const f = nombre === 'login' ? fLog : fReg;
      const primerInput = f.querySelector('input');
      if (primerInput) primerInput.focus();
    }

    tabs.forEach(t => {
      t.addEventListener('click', () => activar(t.dataset.tab));
      t.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
          e.preventDefault();
          const otra = t.dataset.tab === 'login' ? 'registro' : 'login';
          activar(otra);
        }
      });
    });

    fLog.addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = fLog.querySelector('#err-login');
      err.textContent = '';
      const fd = new FormData(fLog);
      try {
        await login(fd.get('usuario'), fd.get('password'));
        alLoguear();
      } catch (ex) { err.textContent = ex.message; }
    });

    fReg.addEventListener('submit', async (e) => {
      e.preventDefault();
      const err = fReg.querySelector('#err-registro');
      err.textContent = '';
      const fd = new FormData(fReg);
      try {
        await registro(fd.get('usuario'), fd.get('password'));
        await login(fd.get('usuario'), fd.get('password'));
        alLoguear();
      } catch (ex) { err.textContent = ex.message; }
    });
  }

  return { comprobarSesion, login, registro, logout, usuario, pintarLogin };
})();
