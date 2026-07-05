# MuniGest

Prototipo de plataforma de tramitación de expedientes electrónicos para Administraciones Locales.

> **Este proyecto ha sido desarrollado como parte del Trabajo Fin de Grado en Ingeniería Informática de la Universidad Internacional de La Rioja (UNIR).**

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Autor

**Carlos Gálvez Reguera**

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Descripción

MuniGest es un prototipo funcional de una plataforma para la gestión de expedientes electrónicos orientada a Administraciones Locales.

La aplicación permite gestionar expedientes administrativos, asociar documentación electrónica, controlar el estado de tramitación, generar un expediente consolidado en formato PDF e integrar la firma electrónica mediante AutoFirma, reproduciendo un flujo administrativo simplificado similar al utilizado en las Administraciones Públicas españolas.

El objetivo del proyecto es demostrar la viabilidad técnica de una solución ligera, modular y fácilmente desplegable que sirva como base para futuros desarrollos de administración electrónica.

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Funcionalidades

- Registro y autenticación de usuarios.
- Gestión de expedientes electrónicos.
- Creación automática de identificadores de expediente.
- Asociación de pasos administrativos a cada expediente.
- Gestión documental mediante documentos PDF y DOCX.
- Conversión automática de documentos DOCX a PDF.
- Generación automática del PDF resumen del expediente.
- Integración con AutoFirma para la firma electrónica.
- Control del ciclo de vida del expediente mediante estados.
- Protección frente a modificaciones de expedientes firmados.
- API REST para la gestión completa del sistema.

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Arquitectura

El sistema sigue una arquitectura modular basada en cuatro capas:

- Presentación (HTML5, CSS3 y JavaScript).
- Lógica de negocio (Python + Flask).
- Persistencia documental mediante ficheros JSON estructurados.
- Integración con AutoFirma para la firma electrónica.

La aplicación se ejecuta localmente sobre Windows mediante un servidor web integrado y puede distribuirse como un ejecutable independiente utilizando PyInstaller.

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Tecnologías utilizadas

- Python 3.10+
- Flask
- HTML5
- CSS3
- JavaScript (ES6)
- bcrypt
- fpdf2
- docx2pdf
- AutoFirma
- PyInstaller

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Requisitos

- Python 3.10 o superior.
- AutoFirma instalado para realizar firmas electrónicas.
- Microsoft Word o LibreOffice para la conversión automática de documentos DOCX a PDF.

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Puesta en marcha

Ejecutar:

```bat
start.bat
```

La aplicación quedará disponible en:

```
http://localhost:8000
```

---

## Estructura del proyecto

```
api/
    app.py
    ...

web/
    pages/
    css/
    js/

data/
    auth.json
    expedientes.json
    expedientes/

start.bat
requirements.txt
run_local.py
```

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Licencia

Este proyecto se distribuye bajo licencia **MIT**.

--------------------------------------------------------------------------------------------------------------------------------------------------------

## Trabajo Fin de Grado

Este repositorio contiene el código fuente desarrollado para el **Trabajo Fin de Grado en Ingeniería Informática** de la **Universidad Internacional de La Rioja (UNIR)**.

El proyecto tiene carácter académico y ha sido desarrollado con fines de investigación.
