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

/* Logica de la app de expedientes: consulta, formulario y firma. */
window.Expedientes = (function () {

  const ESTADOS = {
    borrador: 'Borrador',
    pdf_generado: 'PDF generado',
    firmado: 'Firmado',
  };

  // ============================================================ CONSULTA
  async function pintarConsulta(contenedor) {
    U.montarPlantilla('tpl-consulta', contenedor);
    const fBus = contenedor.querySelector('#form-buscar');
    const inpId = contenedor.querySelector('#bus-id');
    const inpRef = contenedor.querySelector('#bus-ref');
    const btnLimpiar = contenedor.querySelector('#btn-limpiar');
    const lista = contenedor.querySelector('#lista-dir');
    const contador = contenedor.querySelector('#contador-dir');
    const errBox = contenedor.querySelector('#err-listado');

    async function cargar() {
      lista.innerHTML = '<li class="vacio-dir muted"><span class="spin" aria-hidden="true"></span>Cargando...</li>';
      contador.textContent = '';
      errBox.textContent = '';
      const params = new URLSearchParams();
      if (inpId.value.trim()) params.set('id', inpId.value.trim());
      if (inpRef.value.trim()) params.set('q', inpRef.value.trim());
      const qs = params.toString() ? '?' + params.toString() : '';
      try {
        const r = await U.api('GET', '/api/expedientes' + qs);
        contador.textContent = r.items.length + ' elemento' + (r.items.length === 1 ? '' : 's');
        if (!r.items.length) {
          lista.innerHTML = '<li class="vacio-dir muted">No hay expedientes que coincidan con la busqueda.</li>';
          return;
        }
        lista.innerHTML = '';
        r.items.forEach(e => lista.appendChild(itemExp(e, cargar, errBox)));
      } catch (ex) {
        lista.innerHTML = '';
        errBox.textContent = ex.message;
      }
    }

    fBus.addEventListener('submit', (ev) => { ev.preventDefault(); cargar(); });
    btnLimpiar.addEventListener('click', () => {
      inpId.value = ''; inpRef.value = ''; cargar();
    });
    cargar();
  }

  function itemExp(e, recargar, errBox) {
    const li = document.createElement('li');
    const claseEstado = e.estado === 'firmado' ? 'firmado'
                      : e.estado === 'pdf_generado' ? 'pdf' : 'borrador';
    li.className = claseEstado;

    const ico = document.createElement('span');
    ico.className = 'icono';
    ico.setAttribute('aria-hidden', 'true');

    const principal = document.createElement('div');
    principal.className = 'principal';

    const ref = document.createElement('a');
    ref.className = 'ref';
    ref.href = '#expedientes/' + e.id;
    ref.textContent = e.referencia || '(sin referencia)';
    ref.title = e.referencia || '';

    const meta = document.createElement('div');
    meta.className = 'meta';
    const id = document.createElement('span');
    id.className = 'id'; id.textContent = '#' + e.id;
    meta.appendChild(id);

    const adjN = (e.adjuntos || []).length;
    if (adjN > 0) {
      const pill = document.createElement('span');
      pill.className = 'pill';
      pill.innerHTML = '<span class="ico-doc" aria-hidden="true"></span>'
        + adjN + ' adjunto' + (adjN === 1 ? '' : 's');
      meta.appendChild(pill);
    }

    const fecha = document.createElement('span');
    fecha.textContent = 'Modificado ' + U.fmtFecha(e.fecha_modificacion);
    meta.appendChild(fecha);

    principal.append(ref, meta);

    const acciones = document.createElement('div');
    acciones.className = 'acciones-fila';

    const badge = document.createElement('span');
    badge.className = 'badge ' + claseEstado;
    badge.textContent = ESTADOS[e.estado] || e.estado;
    acciones.appendChild(badge);

    if (e.estado !== 'firmado') {
      const btnDel = document.createElement('button');
      btnDel.type = 'button';
      btnDel.className = 'icono-borrar';
      btnDel.setAttribute('aria-label', 'Eliminar expediente ' + e.id);
      btnDel.innerHTML = '<span class="sr-only">Eliminar</span>';
      btnDel.addEventListener('click', async (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        if (!confirm('Eliminar el expediente ' + e.id + '?')) return;
        try {
          await U.api('DELETE', '/api/expedientes/' + e.id);
          recargar();
        } catch (ex) { errBox.textContent = ex.message; }
      });
      acciones.appendChild(btnDel);
    }

    li.append(ico, principal, acciones);
    return li;
  }

  // ============================================================ EXPEDIENTE
  async function pintarExpediente(contenedor, id) {
    U.montarPlantilla('tpl-expediente', contenedor);

    const titulo = contenedor.querySelector('#titulo-exp');
    const subtitulo = contenedor.querySelector('#subtitulo-exp');
    const badgeEstado = contenedor.querySelector('#badge-estado');
    const avisoAF = contenedor.querySelector('#aviso-autofirma');

    const fExp = contenedor.querySelector('#form-exp');
    const inpId = contenedor.querySelector('#exp-id');
    const inpFecha = contenedor.querySelector('#exp-fecha');
    const inpRef = contenedor.querySelector('#exp-ref');
    const txtDesc = contenedor.querySelector('#exp-desc');

    const btnPasos = contenedor.querySelector('#btn-pasos');
    const listaPasos = contenedor.querySelector('#lista-pasos');
    const pasosResumen = contenedor.querySelector('#pasos-resumen');
    const pasosSecciones = contenedor.querySelector('#pasos-secciones');
    const avisoGuardarPasos = contenedor.querySelector('#aviso-guardar-pasos');

    const btnGuardar = contenedor.querySelector('#btn-guardar');
    const btnBorrar = contenedor.querySelector('#btn-borrar');
    const infoExp = contenedor.querySelector('#info-exp');
    const errExp = contenedor.querySelector('#err-exp');

    const zonaAdj = contenedor.querySelector('#zona-adjuntos');
    const fAdj = contenedor.querySelector('#form-adjunto');
    const inpAdj = contenedor.querySelector('#input-adjunto');
    const lblAdj = contenedor.querySelector('#adj-elegido');
    const btnSubirAdj = contenedor.querySelector('#btn-subir-adj');
    const infoAdj = contenedor.querySelector('#info-adj');
    const errAdj = contenedor.querySelector('#err-adj');
    const listaAdjuntos = contenedor.querySelector('#lista-adjuntos');

    const zonaFirma = contenedor.querySelector('#zona-firma');
    const btnGenerar = contenedor.querySelector('#btn-generar');
    const btnVerPdf = contenedor.querySelector('#btn-ver-pdf');
    const zonaFirmar = contenedor.querySelector('#zona-firmar');
    const selCert = contenedor.querySelector('#sel-cert');
    const avisoCert = contenedor.querySelector('#aviso-cert');
    const btnFirmar = contenedor.querySelector('#btn-firmar');
    const bloqueFirmado = contenedor.querySelector('#bloque-firmado');
    const btnVerFirmado = contenedor.querySelector('#btn-ver-firmado');
    const infoFirma = contenedor.querySelector('#info-firma');
    const errFirma = contenedor.querySelector('#err-firma');

    let estado = null;          // expediente actual del backend
    let pasosCatalogo = [];     // catalogo de pasos administrativos
    // pasosLocal: lista [{nombre, documentos}] que se va a mandar al guardar
    let pasosLocal = [];

    function indicePaso(nombre) {
      return pasosLocal.findIndex(p => p.nombre === nombre);
    }

    function renderResumenPasos() {
      const n = pasosLocal.length;
      pasosResumen.textContent = n === 0
        ? 'Selecciona los pasos...'
        : (n + ' paso' + (n === 1 ? '' : 's') + ' seleccionado' + (n === 1 ? '' : 's'));
      renderSeccionesPasos();
    }

    function renderSeccionesPasos() {
      pasosSecciones.innerHTML = '';
      const tieneId = !!(estado && estado.id);
      const firmado = !!(estado && estado.estado === 'firmado');
      pasosLocal.forEach((paso, idx) => {
        const sec = document.createElement('section');
        sec.className = 'paso-seccion';
        const docs = paso.documentos || [];
        sec.dataset.vacio = docs.length === 0 ? 'true' : 'false';

        const head = document.createElement('header');
        const num = document.createElement('span');
        num.className = 'num'; num.textContent = String(idx + 1);
        const h = document.createElement('h4'); h.textContent = paso.nombre;
        head.append(num, h);
        if (!firmado) {
          const x = document.createElement('button');
          x.type = 'button'; x.className = 'quitar';
          x.setAttribute('aria-label', 'Quitar paso ' + paso.nombre);
          x.textContent = 'x';
          x.addEventListener('click', () => quitarPaso(paso.nombre));
          head.appendChild(x);
        }
        sec.appendChild(head);

        const cont = document.createElement('div');
        cont.className = 'contenido';

        const ul = document.createElement('ul');
        ul.className = 'lista-docs-paso';
        if (!docs.length) {
          const li = document.createElement('li');
          li.className = 'vacio';
          li.textContent = tieneId
            ? 'Sin documentos. Adjunta los necesarios para este paso.'
            : 'Guarda el expediente para poder anadir documentos.';
          ul.appendChild(li);
        } else {
          docs.forEach((d, j) => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = d.url; a.target = '_blank'; a.rel = 'noopener';
            a.textContent = d.nombre_original || d.archivo;
            const meta = document.createElement('span');
            meta.className = 'meta';
            meta.textContent = U.fmtBytes(d.tamano) + ' - ' + U.fmtFecha(d.subido);
            li.append(a, meta);
            if (!firmado) {
              const del = document.createElement('button');
              del.type = 'button'; del.className = 'icono-borrar';
              del.setAttribute('aria-label', 'Eliminar documento');
              del.innerHTML = '<span class="sr-only">Eliminar</span>';
              del.addEventListener('click', () => borrarDocPaso(idx, j, d.nombre_original));
              li.appendChild(del);
            }
            ul.appendChild(li);
          });
        }
        cont.appendChild(ul);

        if (!firmado) {
          const sub = document.createElement('div');
          sub.className = 'subida-paso';
          const inp = document.createElement('input');
          inp.type = 'file';
          inp.accept = 'application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
          inp.disabled = !tieneId;
          const bt = document.createElement('button');
          bt.type = 'button'; bt.className = 'btn';
          bt.textContent = 'Anadir documento';
          bt.disabled = !tieneId;
          if (!tieneId) bt.title = 'Guarda el expediente primero';
          bt.addEventListener('click', () => subirDocPaso(idx, inp, sub));
          sub.append(inp, bt);
          const info = document.createElement('p'); info.className = 'info-paso';
          const err = document.createElement('p'); err.className = 'err-paso';
          cont.appendChild(sub);
          cont.appendChild(info);
          cont.appendChild(err);
        }

        sec.appendChild(cont);
        pasosSecciones.appendChild(sec);
      });

      if (avisoGuardarPasos) {
        avisoGuardarPasos.style.display = tieneId ? 'none' : '';
      }
    }

    function quitarPaso(nombre) {
      const i = indicePaso(nombre);
      if (i < 0) return;
      const docs = pasosLocal[i].documentos || [];
      if (docs.length && !confirm('Este paso tiene ' + docs.length + ' documento(s). Si quitas el paso se eliminaran. Continuar?')) return;
      pasosLocal.splice(i, 1);
      const cb = listaPasos.querySelector('input[data-p="' + CSS.escape(nombre) + '"]');
      if (cb) cb.checked = false;
      renderResumenPasos();
    }

    async function subirDocPaso(idx, inp, contenedorSubida) {
      const info = contenedorSubida.parentElement.querySelector('.info-paso');
      const err = contenedorSubida.parentElement.querySelector('.err-paso');
      info.textContent = ''; err.textContent = '';
      if (!inp.files[0]) { err.textContent = 'Selecciona un archivo.'; return; }
      if (!estado || !estado.id) { err.textContent = 'Guarda el expediente primero.'; return; }
      const fd = new FormData(); fd.append('archivo', inp.files[0]);
      info.innerHTML = '<span class="spin" aria-hidden="true"></span>Subiendo y procesando...';
      try {
        const r = await U.api(
          'POST',
          '/api/expedientes/' + estado.id + '/pasos/' + idx + '/documentos',
          { form: fd }
        );
        aplicarEstado(r);
      } catch (ex) {
        info.textContent = '';
        err.textContent = ex.message;
      }
    }

    async function borrarDocPaso(idx, didx, nombre) {
      if (!confirm('Eliminar el documento ' + (nombre || '') + '?')) return;
      try {
        const r = await U.api(
          'DELETE',
          '/api/expedientes/' + estado.id + '/pasos/' + idx + '/documentos/' + didx
        );
        aplicarEstado(r);
      } catch (ex) {
        errExp.textContent = ex.message;
      }
    }

    async function cargarPasos() {
      try {
        const r = await U.api('GET', '/api/pasos');
        pasosCatalogo = r.items || [];
      } catch (e) {
        pasosCatalogo = [];
      }
      listaPasos.innerHTML = '';
      pasosCatalogo.forEach(p => {
        const li = document.createElement('li');
        li.setAttribute('role', 'option');
        const lbl = document.createElement('label');
        lbl.className = 'opcion-paso';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.dataset.p = p;
        cb.addEventListener('change', () => {
          const i = indicePaso(p);
          if (cb.checked) {
            if (i < 0) pasosLocal.push({ nombre: p, documentos: [] });
          } else {
            if (i >= 0) {
              const docs = pasosLocal[i].documentos || [];
              if (docs.length && !confirm('Este paso tiene ' + docs.length + ' documento(s). Si lo quitas se eliminaran. Continuar?')) {
                cb.checked = true;
                return;
              }
              pasosLocal.splice(i, 1);
            }
          }
          li.setAttribute('aria-selected', cb.checked ? 'true' : 'false');
          renderResumenPasos();
        });
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(' ' + p));
        li.appendChild(lbl);
        listaPasos.appendChild(li);
      });
    }

    function abrirPasos(abrir) {
      listaPasos.classList.toggle('oculto', !abrir);
      btnPasos.setAttribute('aria-expanded', abrir ? 'true' : 'false');
    }
    btnPasos.addEventListener('click', () => {
      abrirPasos(btnPasos.getAttribute('aria-expanded') !== 'true');
    });
    document.addEventListener('click', (e) => {
      if (!btnPasos.contains(e.target) && !listaPasos.contains(e.target)) abrirPasos(false);
    });
    btnPasos.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') abrirPasos(false);
    });

    // -------- Aplicar estado del expediente al UI
    function aplicarEstado(exp) {
      estado = exp;
      if (exp) {
        titulo.textContent = 'Expediente N.o ' + exp.id;
        subtitulo.textContent = 'Creado el ' + U.fmtFecha(exp.fecha_creacion)
          + ' por ' + (exp.usuario || '');
        inpId.value = exp.id;
        inpFecha.value = U.fmtFecha(exp.fecha_creacion);
        inpRef.value = exp.referencia || '';
        txtDesc.value = exp.descripcion || '';

        // Los pasos vienen del backend como [{nombre, documentos:[...]}]
        pasosLocal = (exp.pasos || []).map(p => ({
          nombre: p.nombre || '',
          documentos: (p.documentos || []).slice(),
        }));
        const nombres = new Set(pasosLocal.map(p => p.nombre));
        listaPasos.querySelectorAll('input[type=checkbox]').forEach(cb => {
          cb.checked = nombres.has(cb.dataset.p);
          cb.parentElement.parentElement.setAttribute(
            'aria-selected', cb.checked ? 'true' : 'false');
        });
        renderResumenPasos();

        const claseEstado = exp.estado === 'firmado' ? 'firmado'
                          : exp.estado === 'pdf_generado' ? 'pdf' : 'borrador';
        badgeEstado.className = 'badge ' + claseEstado;
        badgeEstado.textContent = ESTADOS[exp.estado] || exp.estado;

        zonaAdj.classList.remove('oculto');
        zonaFirma.classList.remove('oculto');
        btnBorrar.classList.toggle('oculto', exp.estado === 'firmado');

        // Bloqueo si firmado
        const firmado = exp.estado === 'firmado';
        inpRef.readOnly = firmado;
        txtDesc.readOnly = firmado;
        btnPasos.disabled = firmado;
        btnGuardar.disabled = firmado;
        btnSubirAdj.disabled = firmado;
        inpAdj.disabled = firmado;

        renderAdjuntos(exp.adjuntos || []);
        renderFirma(exp);
      } else {
        // creando
        titulo.textContent = 'Nuevo expediente';
        subtitulo.textContent = 'Rellena los datos. El ID se asignara automaticamente.';
        inpId.value = '(sin asignar)';
        inpFecha.value = '(al guardar)';
        badgeEstado.className = 'badge borrador';
        badgeEstado.textContent = 'Nuevo';
        zonaAdj.classList.add('oculto');
        zonaFirma.classList.add('oculto');
        btnBorrar.classList.add('oculto');
        pasosLocal = [];
        listaPasos.querySelectorAll('input[type=checkbox]').forEach(cb => cb.checked = false);
        renderResumenPasos();
      }
    }

    function renderAdjuntos(adjs) {
      listaAdjuntos.innerHTML = '';
      if (!adjs.length) {
        const li = document.createElement('li');
        li.className = 'muted';
        li.textContent = 'Aun no hay documentos adjuntos.';
        listaAdjuntos.appendChild(li);
        return;
      }
      adjs.forEach((a, i) => {
        const li = document.createElement('li');
        const link = document.createElement('a');
        link.href = a.url; link.target = '_blank'; link.rel = 'noopener';
        link.textContent = a.nombre_original || a.archivo;
        const meta = document.createElement('span');
        meta.className = 'meta';
        meta.textContent = U.fmtBytes(a.tamano) + ' - ' + U.fmtFecha(a.subido);
        li.append(link, meta);
        if (estado.estado !== 'firmado') {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'icono-borrar';
          btn.setAttribute('aria-label', 'Eliminar adjunto ' + (a.nombre_original || ''));
          btn.innerHTML = '<span class="sr-only">Eliminar</span>';
          btn.addEventListener('click', async () => {
            if (!confirm('Eliminar el adjunto?')) return;
            try {
              const r = await U.api('DELETE', '/api/expedientes/' + estado.id + '/adjuntos/' + i);
              aplicarEstado(r);
            } catch (ex) { errAdj.textContent = ex.message; }
          });
          li.appendChild(btn);
        }
        listaAdjuntos.appendChild(li);
      });
    }

    function renderFirma(exp) {
      btnVerPdf.classList.toggle('oculto', !exp.pdf_url);
      if (exp.pdf_url) btnVerPdf.href = exp.pdf_url;
      bloqueFirmado.classList.toggle('oculto', exp.estado !== 'firmado');
      if (exp.firmado_url) btnVerFirmado.href = exp.firmado_url;
      // mostrar zona de firmar solo si hay PDF y no esta firmado
      const puedeFirmar = exp.estado === 'pdf_generado';
      zonaFirmar.classList.toggle('oculto', !puedeFirmar);
      btnGenerar.disabled = exp.estado === 'firmado';
      if (puedeFirmar && !selCert.dataset.cargado) {
        cargarCertificados();
      }
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
          // En Windows sabemos que no hay certificados: avisar y bloquear.
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
        selCert.dataset.cargado = '1';
      } catch (e) {
        selCert.innerHTML = '<option value="">(seleccionar en AutoFirma)</option>';
        avisoCert.textContent = 'No se pudo obtener la lista: ' + e.message;
      }
    }

    async function comprobarAutoFirma() {
      avisoAF.classList.add('oculto'); avisoAF.classList.remove('error'); avisoAF.textContent = '';
      try {
        const r = await U.api('GET', '/api/autofirma/estado');
        if (!r.instalado) {
          avisoAF.textContent = 'AutoFirma no esta instalado en este equipo. '
            + 'Descarguelo desde firmaelectronica.gob.es';
          avisoAF.classList.add('error');
          avisoAF.classList.remove('oculto');
          return false;
        }
      } catch (e) {
        avisoAF.textContent = 'No se pudo comprobar AutoFirma.';
        avisoAF.classList.add('error');
        avisoAF.classList.remove('oculto');
        return false;
      }
      return true;
    }

    // -------- Submits y acciones
    fExp.addEventListener('submit', async (e) => {
      e.preventDefault();
      errExp.textContent = ''; infoExp.textContent = '';
      const cuerpo = {
        referencia: inpRef.value.trim(),
        descripcion: txtDesc.value.trim(),
        pasos: pasosLocal.map(p => p.nombre),
      };
      if (!cuerpo.referencia) {
        errExp.textContent = 'La referencia es obligatoria.';
        inpRef.focus(); return;
      }
      btnGuardar.disabled = true;
      try {
        if (estado && estado.id) {
          const r = await U.api('PUT', '/api/expedientes/' + estado.id, { json: cuerpo });
          aplicarEstado(r);
          infoExp.textContent = 'Cambios guardados.';
        } else {
          const r = await U.api('POST', '/api/expedientes', { json: cuerpo });
          location.hash = '#expedientes/' + r.id;
        }
      } catch (ex) {
        errExp.textContent = ex.message;
      } finally {
        btnGuardar.disabled = false;
      }
    });

    btnBorrar.addEventListener('click', async () => {
      if (!estado) return;
      if (!confirm('Eliminar el expediente ' + estado.id + '? Esta accion no se puede deshacer.')) return;
      try {
        await U.api('DELETE', '/api/expedientes/' + estado.id);
        location.hash = '#expedientes';
      } catch (ex) { errExp.textContent = ex.message; }
    });

    inpAdj.addEventListener('change', () => {
      lblAdj.textContent = inpAdj.files[0] ? inpAdj.files[0].name : '';
    });
    fAdj.addEventListener('submit', async (e) => {
      e.preventDefault();
      errAdj.textContent = ''; infoAdj.textContent = '';
      if (!inpAdj.files[0]) { errAdj.textContent = 'Selecciona un archivo.'; return; }
      if (!estado || !estado.id) { errAdj.textContent = 'Guarda el expediente primero.'; return; }
      const fd = new FormData(); fd.append('archivo', inpAdj.files[0]);
      btnSubirAdj.disabled = true;
      infoAdj.innerHTML = '<span class="spin" aria-hidden="true"></span>Subiendo y procesando...';
      try {
        const r = await U.api('POST', '/api/expedientes/' + estado.id + '/adjuntos', { form: fd });
        aplicarEstado(r);
        fAdj.reset(); lblAdj.textContent = '';
        infoAdj.textContent = 'Adjunto subido.';
      } catch (ex) {
        infoAdj.textContent = '';
        errAdj.textContent = ex.message;
      } finally {
        btnSubirAdj.disabled = false;
      }
    });

    btnGenerar.addEventListener('click', async () => {
      errFirma.textContent = ''; infoFirma.textContent = '';
      if (!estado || !estado.id) return;
      btnGenerar.disabled = true;
      infoFirma.innerHTML = '<span class="spin" aria-hidden="true"></span>Generando PDF...';
      try {
        const r = await U.api('POST', '/api/expedientes/' + estado.id + '/generar');
        aplicarEstado(r);
        infoFirma.textContent = 'PDF generado.';
      } catch (ex) {
        infoFirma.textContent = '';
        errFirma.textContent = ex.message;
      } finally {
        btnGenerar.disabled = false;
      }
    });

    btnFirmar.addEventListener('click', async () => {
      errFirma.textContent = ''; infoFirma.textContent = '';
      const ok = await comprobarAutoFirma();
      if (!ok) return;
      btnFirmar.disabled = true;
      infoFirma.innerHTML = '<span class="spin" aria-hidden="true"></span>'
        + (selCert.value
            ? 'Firmando con el certificado seleccionado...'
            : 'Abriendo AutoFirma para que selecciones el certificado...');
      try {
        const r = await U.api('POST', '/api/expedientes/' + estado.id + '/firmar',
                              { json: { thumbprint: selCert.value || '' } });
        aplicarEstado(r);
        infoFirma.textContent = '';
        bloqueFirmado.focus();
      } catch (ex) {
        infoFirma.textContent = '';
        errFirma.textContent = ex.message;
      } finally {
        btnFirmar.disabled = false;
      }
    });

    // ---- Init
    await cargarPasos();
    if (id) {
      try {
        const exp = await U.api('GET', '/api/expedientes/' + id);
        aplicarEstado(exp);
      } catch (ex) {
        errExp.textContent = ex.message;
        aplicarEstado(null);
      }
    } else {
      aplicarEstado(null);
    }
    comprobarAutoFirma();
  }

  return { pintarConsulta, pintarExpediente };
})();
