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

(async function () {
  const app = document.getElementById('app');

  function rutaActual() {
    const h = (location.hash || '#expedientes').replace(/^#/, '');
    const partes = h.split('/').filter(Boolean);
    return {
      seccion: partes[0] || 'expedientes',
      sub: partes[1] || null,
    };
  }

  function pintarShell() {
    app.innerHTML = '';
    U.montarPlantilla('tpl-header', app);
    if (window.Tema) Tema.activar();
    document.getElementById('lbl-usuario').textContent = Auth.usuario() || '';
    document.getElementById('btn-logout').addEventListener('click', async () => {
      await Auth.logout();
      pintarLogin();
    });
    app.querySelectorAll('.nav a').forEach(a => {
      a.addEventListener('click', () => setTimeout(enrutar, 0));
    });
    const main = document.createElement('main');
    main.id = 'contenido';
    main.tabIndex = -1;
    app.appendChild(main);
    enrutar();
  }

  function actualizarNav(seccion, sub) {
    let id;
    if (seccion === 'documentos') id = 'documentos';
    else if (seccion === 'expedientes' && sub === 'nuevo') id = 'expedientes/nuevo';
    else id = 'expedientes';
    document.querySelectorAll('.nav a').forEach(a => {
      if (a.dataset.ruta === id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }

  function enrutar() {
    const contenido = document.getElementById('contenido');
    if (!contenido) return;
    const { seccion, sub } = rutaActual();
    actualizarNav(seccion, sub);

    if (seccion === 'documentos') {
      Documentos.pintar(contenido);
    } else if (seccion === 'expedientes') {
      if (sub === 'nuevo') {
        Expedientes.pintarExpediente(contenido, null);
      } else if (sub) {
        Expedientes.pintarExpediente(contenido, sub);
      } else {
        Expedientes.pintarConsulta(contenido);
      }
    } else {
      Expedientes.pintarConsulta(contenido);
    }
  }

  function pintarLogin() {
    app.innerHTML = '';
    Auth.pintarLogin(app, pintarShell);
  }

  window.addEventListener('hashchange', enrutar);

  const usuario = await Auth.comprobarSesion();
  if (usuario) pintarShell(); else pintarLogin();
})();
