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

/* Pagina "Firmar documento": subida + firma de un PDF/DOCX suelto. */
window.Documentos = (function () {

  const ESTADOS = {
    pdf_generado: 'Pendiente de firma',
    firmado: 'Firmado',
  };

  let docActivo = null; // documento que se va a firmar
  let certsCargados = false;

  async function comprobarAutoFirma(elemAviso) {
    elemAviso.classList.add('oculto');
    elemAviso.classList.remove('error');
    elemAviso.textContent = '';
    try {
      const r = await U.api('GET', '/api/autofirma/estado');
      if (!r.instalado) {
        elemAviso.textContent =
          'AutoFirma no esta instalado en este equipo. Descarguelo desde firmaelectronica.gob.es.';
        elemAviso.classList.add('error');
        elemAviso.classList.remove('oculto');
        return false;
      }
    } catch (e) {
      elemAviso.textContent = 'No se pudo comprobar AutoFirma.';
      elemAviso.classList.add('error');
      elemAviso.classList.remove('oculto');
      return false;
    }
    return true;
  }

  async function pintar(contenedor) {
    U.montarPlantilla('tpl-documentos', contenedor);

    const aviso = contenedor.querySelector('#aviso-autofirma');
    const fDoc = contenedor.querySelector('#form-doc');
    const inp = contenedor.querySelector('#input-doc');
    const lbl = contenedor.querySelector('#doc-elegido');
    const btnSubir = contenedor.querySelector('#btn-subir-doc');
    const info = contenedor.querySelector('#info-doc');
    const err = contenedor.querySelector('#err-doc');

    const tb = contenedor.querySelector('#tb-docs');
    const errLista = contenedor.querySelector('#err-listado-docs');

    const zonaFirmar = contenedor.querySelector('#zona-firmar-doc');
    const firmarNombre = contenedor.querySelector('#firmar-doc-nombre');
    const selCert = contenedor.querySelector('#sel-cert-doc');
    const avisoCert = contenedor.querySelector('#aviso-cert-doc');
    const btnFirmar = contenedor.querySelector('#btn-firmar-doc');
    const btnCancelar = contenedor.querySelector('#btn-cancelar-firma-doc');
    const infoFirma = contenedor.querySelector('#info-firma-doc');
    const errFirma = contenedor.querySelector('#err-firma-doc');

    docActivo = null;
    certsCargados = false;

    comprobarAutoFirma(aviso);

    inp.addEventListener('change', () => {
      lbl.textContent = inp.files[0] ? inp.files[0].name : '';
    });

    fDoc.addEventListener('submit', async (e) => {
      e.preventDefault();
      err.textContent = ''; info.textContent = '';
      if (!inp.files[0]) { err.textContent = 'Selecciona un archivo.'; return; }
      const fd = new FormData(); fd.append('archivo', inp.files[0]);
      btnSubir.disabled = true;
      info.innerHTML = '<span class="spin" aria-hidden="true"></span>Subiendo y procesando...';
      try {
        await U.api('POST', '/api/documentos', { form: fd });
        info.textContent = 'Documento subido.';
        fDoc.reset(); lbl.textContent = '';
        cargarLista();
      } catch (ex) {
        info.textContent = '';
        err.textContent = ex.message;
      } finally {
        btnSubir.disabled = false;
      }
    });

    async function cargarLista() {
      tb.innerHTML = '<tr><td colspan="4" class="muted"><span class="spin" aria-hidden="true"></span>Cargando...</td></tr>';
      errLista.textContent = '';
      try {
        const r = await U.api('GET', '/api/documentos');
        if (!r.items.length) {
          tb.innerHTML = '<tr><td colspan="4" class="muted">No tienes documentos. Sube uno arriba.</td></tr>';
          return;
        }
        tb.innerHTML = '';
        r.items.forEach(d => tb.appendChild(filaDoc(d)));
      } catch (ex) {
        tb.innerHTML = '';
        errLista.textContent = ex.message;
      }
    }

    function filaDoc(d) {
      const tr = document.createElement('tr');

      const tdN = document.createElement('td');
      const a = document.createElement('a');
      a.href = (d.firmado_url || d.pdf_url || '#');
      a.target = '_blank'; a.rel = 'noopener';
      a.textContent = d.nombre_original;
      tdN.appendChild(a);

      const tdEst = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge ' + (d.estado === 'firmado' ? 'firmado' : 'pdf');
      badge.textContent = ESTADOS[d.estado] || d.estado;
      tdEst.appendChild(badge);

      const tdFecha = document.createElement('td');
      tdFecha.textContent = U.fmtFecha(d.fecha_firma || d.fecha_subida);

      const tdAcc = document.createElement('td');
      tdAcc.style.display = 'flex';
      tdAcc.style.gap = '.4rem';
      tdAcc.style.flexWrap = 'wrap';

      if (d.estado === 'firmado') {
        const ver = document.createElement('a');
        ver.className = 'btn'; ver.textContent = 'Ver firmado';
        ver.href = d.firmado_url; ver.target = '_blank'; ver.rel = 'noopener';
        tdAcc.appendChild(ver);
      } else {
        const firm = document.createElement('button');
        firm.type = 'button'; firm.className = 'btn primario';
        firm.textContent = 'Firmar';
        firm.addEventListener('click', () => abrirFirma(d));
        tdAcc.appendChild(firm);
        const ver = document.createElement('a');
        ver.className = 'btn'; ver.textContent = 'Ver';
        ver.href = d.pdf_url; ver.target = '_blank'; ver.rel = 'noopener';
        tdAcc.appendChild(ver);
        const del = document.createElement('button');
        del.type = 'button'; del.className = 'icono-borrar';
        del.setAttribute('aria-label', 'Eliminar ' + d.nombre_original);
        del.innerHTML = '<span class="sr-only">Eliminar</span>';
        del.addEventListener('click', async () => {
          if (!confirm('Eliminar ' + d.nombre_original + '?')) return;
          try {
            await U.api('DELETE', '/api/documentos/' + d.id);
            cargarLista();
          } catch (ex) { errLista.textContent = ex.message; }
        });
        tdAcc.appendChild(del);
      }

      tr.append(tdN, tdEst, tdFecha, tdAcc);
      return tr;
    }

    async function cargarCertificados() {
      selCert.innerHTML = '<option value="">Cargando certificados...</option>';
      avisoCert.textContent = '';
      btnFirmar.disabled = false;
      try {
        const r = await U.api('GET', '/api/certificados');
        selCert.innerHTML = '<option value="">(seleccionar en AutoFirma)</option>';
        if (!r.soportado) {
          avisoCert.textContent = 'En este sistema operativo se elegira el certificado en la ventana de AutoFirma.';
        } else if (!r.items.length) {
          selCert.innerHTML = '<option value="">(sin certificados)</option>';
          selCert.disabled = true;
          btnFirmar.disabled = true;
          avisoCert.textContent = 'Certificados no encontrados. Instala un certificado digital en el almacen de Windows para poder firmar.';
        } else {
          selCert.disabled = false;
          r.items.forEach(c => {
            const o = document.createElement('option');
            o.value = c.thumbprint;
            const exp = c.expira ? ' - caduca ' + new Date(c.expira).toLocaleDateString('es-ES') : '';
            o.textContent = c.nombre + exp;
            selCert.appendChild(o);
          });
        }
        certsCargados = true;
      } catch (ex) {
        selCert.innerHTML = '<option value="">(seleccionar en AutoFirma)</option>';
        avisoCert.textContent = 'No se pudo obtener la lista: ' + ex.message;
      }
    }

    function abrirFirma(d) {
      docActivo = d;
      firmarNombre.textContent = d.nombre_original;
      errFirma.textContent = ''; infoFirma.textContent = '';
      zonaFirmar.classList.remove('oculto');
      if (!certsCargados) cargarCertificados();
      zonaFirmar.scrollIntoView({ behavior: 'smooth', block: 'start' });
      zonaFirmar.focus();
    }

    btnCancelar.addEventListener('click', () => {
      docActivo = null;
      zonaFirmar.classList.add('oculto');
    });

    btnFirmar.addEventListener('click', async () => {
      if (!docActivo) return;
      errFirma.textContent = ''; infoFirma.textContent = '';
      const ok = await comprobarAutoFirma(aviso);
      if (!ok) return;
      btnFirmar.disabled = true;
      infoFirma.innerHTML = '<span class="spin" aria-hidden="true"></span>'
        + (selCert.value
            ? 'Firmando con el certificado seleccionado...'
            : 'Abriendo AutoFirma para que selecciones el certificado...');
      try {
        await U.api('POST', '/api/documentos/' + docActivo.id + '/firmar',
                    { json: { thumbprint: selCert.value || '' } });
        infoFirma.textContent = '';
        zonaFirmar.classList.add('oculto');
        docActivo = null;
        cargarLista();
      } catch (ex) {
        infoFirma.textContent = '';
        errFirma.textContent = ex.message;
      } finally {
        btnFirmar.disabled = false;
      }
    });

    cargarLista();
  }

  return { pintar };
})();
