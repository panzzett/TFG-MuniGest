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

// Utilidades comunes
window.U = (function () {
  async function api(metodo, ruta, opciones) {
    opciones = opciones || {};
    const cabeceras = opciones.headers || {};
    const init = { method: metodo, credentials: 'same-origin', headers: cabeceras };
    if (opciones.json !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opciones.json);
    } else if (opciones.form) {
      init.body = opciones.form;
    }
    const r = await fetch(ruta, init);
    let data = null;
    const ct = r.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      data = await r.json().catch(() => null);
    }
    if (!r.ok) {
      const err = new Error((data && (data.error || data.detalle)) || ('Error ' + r.status));
      err.status = r.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function fmtBytes(n) {
    if (!n) return '0 B';
    const k = 1024, u = ['B','KB','MB','GB'];
    const i = Math.min(Math.floor(Math.log(n) / Math.log(k)), u.length - 1);
    return (n / Math.pow(k, i)).toFixed(i ? 1 : 0) + ' ' + u[i];
  }

  function fmtFecha(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-ES');
  }

  function montarPlantilla(idTpl, contenedor) {
    const tpl = document.getElementById(idTpl);
    if (!tpl) return null;
    contenedor.innerHTML = '';
    contenedor.appendChild(tpl.content.cloneNode(true));
    return contenedor;
  }

  return { api, fmtBytes, fmtFecha, montarPlantilla };
})();
