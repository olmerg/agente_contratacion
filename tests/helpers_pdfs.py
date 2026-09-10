from fpdf import FPDF

PLIEGO_A = [
    "PLIEGO DE CONDICIONES LOTE 1",
    "El objeto es la adquisicion de licencias de software de arquitectura.",
    "El proponente debe acreditar soporte tecnico y mantenimiento.",
    "El plazo de ejecucion es de doce meses.",
]

PLIEGO_B = [
    "LOTE 2 ACTUALIZACION DE SOFTWARE",
    "Se solicitan licencias de diseno y produccion audiovisual.",
    "El contratista entregara capacitacion al personal de la entidad.",
    "El valor estimado es de doscientos millones de pesos.",
]


def crear_pdf(ruta, lineas):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for linea in lineas:
        pdf.cell(0, 6, linea.encode("latin-1", errors="replace").decode("latin-1"))
        pdf.ln()
    pdf.output(str(ruta))