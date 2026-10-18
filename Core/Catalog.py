"""Listas blancas del catálogo (departamentos, categorías, condición, filtros y orden).

Las categorías se guardan como slug en inglés (como el ítem de ejemplo de la Parte 5,
`computer-accessories`) y se muestran con las etiquetas en español de la Parte 4.
Cada categoría tiene un ícono (sprite SVG en View/SharedViews/HTML/Base.html) y un color
(clase CSS cat-<slug>).
"""

DEPARTMENTS = {
    "electronics": "Electrónica",
    "home-office": "Hogar y Oficina",
}

DEPARTMENT_BLURBS = {
    "electronics": "Computadoras, monitores, audio, redes y accesorios.",
    "home-office": "Todo para trabajar cómodo en casa.",
}

# slug: (etiqueta, departamento, ícono)
CATEGORIES = {
    "monitors": ("Monitores", "electronics", "monitor"),
    "computers": ("Computadoras", "electronics", "laptop"),
    "storage": ("Almacenamiento", "electronics", "drive"),
    "networking": ("Redes", "electronics", "wifi"),
    "computer-accessories": ("Accesorios", "electronics", "mouse"),
    "audio": ("Audio", "electronics", "headphones"),
    "office": ("Oficina", "home-office", "chair"),
}

CATEGORY_CHOICES = [(slug, label) for slug, (label, _dept, _icon) in CATEGORIES.items()]
DEPARTMENT_CHOICES = list(DEPARTMENTS.items())

CONDITIONS = {
    "NEW": "Nuevo",
    "USED": "Usado",
    "REFURBISHED": "Reacondicionado",
}
CONDITION_CHOICES = list(CONDITIONS.items())

# Disponibilidad (filtro del catálogo); "pocas" = 1 a 5 unidades.
LOW_STOCK = 5
AVAILABILITY = {
    "in_stock": "Disponible",
    "few_left": "Últimas piezas",
    "sold_out": "Agotado",
}
AVAILABILITY_CHOICES = list(AVAILABILITY.items())

SORTS = {
    "newest": "Más recientes",
    "rating": "Mejor calificados",
    "best_selling": "Más vendidos",
    "price_asc": "Precio: menor a mayor",
    "price_desc": "Precio: mayor a menor",
    "name": "Nombre (A-Z)",
}
SORT_CHOICES = list(SORTS.items())


def category_label(slug):
    entry = CATEGORIES.get(slug)
    return entry[0] if entry else "Otra"


def category_icon(slug):
    entry = CATEGORIES.get(slug)
    return entry[2] if entry else "box"


def category_class(slug):
    """Clase CSS segura: solo slugs de la lista blanca (nunca texto arbitrario)."""
    return f"cat-{slug}" if slug in CATEGORIES else "cat-other"


def department_of(slug):
    entry = CATEGORIES.get(slug)
    return entry[1] if entry else None


def department_label(slug_or_category):
    if slug_or_category in DEPARTMENTS:
        return DEPARTMENTS[slug_or_category]
    dept = department_of(slug_or_category)
    return DEPARTMENTS.get(dept, "Otros")


def categories_of(department):
    return [slug for slug, (_l, dept, _i) in CATEGORIES.items() if dept == department]


def availability_of(stock):
    if stock <= 0:
        return "sold_out"
    if stock <= LOW_STOCK:
        return "few_left"
    return "in_stock"


def initials(name):
    """Dos letras para la miniatura del producto (sin imágenes externas)."""
    words = [w for w in (name or "").split() if w[:1].isalnum()]
    if not words:
        return "··"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


# ---------------------------------------------------------------- envíos
# Estados de México (los mismos que acepta la Lambda lambdaCreateOrder: MX_STATES).
MX_STATES = (
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas",
    "Chihuahua", "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México",
    "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán", "Morelos", "Nayarit",
    "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
)
