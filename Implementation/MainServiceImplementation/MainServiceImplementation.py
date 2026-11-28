"""Implementación del servicio principal: portada pública y panel de administración."""
from Core.Catalog import DEPARTMENTS, categories_of, department_of
from Core.Extensions import db
from Implementation.SharedImplementation import StoredProcedures
from Implementation.SharedImplementation.AccountQueries import seller_display_names
from Interfaces.MainServiceInterface.IMainService import IMainService
from Interfaces.MainServiceInterface.MainDTO import AdminDashboardDTO, HomeDTO
from Models import AdminAction, AuthEvent, User

LATEST_LIMIT = 8
FAILED_LOGIN_EVENTS = ("login_failed", "login_lockout", "login_locked")


class MainServiceImplementation(IMainService):
    def __init__(self, product_service):
        # Depende de la INTERFAZ del servicio de productos, no del API directamente.
        self.products = product_service

    @staticmethod
    def _summary(active):
        departments = []
        for slug, label in DEPARTMENTS.items():
            in_dept = [p for p in active if department_of(p.category) == slug]
            cats = [(c, sum(1 for p in in_dept if p.category == c)) for c in categories_of(slug)]
            departments.append({"slug": slug, "label": label, "count": len(in_dept), "categories": cats})
        stats = {
            "products": len(active),
            "categories": len({p.category for p in active}),
            "in_stock": sum(1 for p in active if p.stock > 0),
            "sellers": len({p.seller_id for p in active}),
        }
        return departments, stats

    def home(self, viewer):
        products = self.products.list_all_products()
        active = [p for p in products if p.status == "ACTIVE"]
        departments, stats = self._summary(active)
        latest = sorted(active, key=lambda p: (p.created_at, p.product_id), reverse=True)[:LATEST_LIMIT]
        recommended = sorted(active, key=lambda p: (p.rating_avg, p.rating_count, p.sales_count, p.product_id),
                             reverse=True)[:LATEST_LIMIT]
        shop = None
        if viewer.is_authenticated and viewer.seller_id:
            mine = [p for p in products if p.seller_id == viewer.seller_id and p.status != "DELISTED"]
            shop = {
                "count": len(mine),
                "active": sum(1 for p in mine if p.status == "ACTIVE"),
                "blocked": sum(1 for p in mine if p.status == "BLOCKED"),
                "low": sum(1 for p in mine if p.status == "ACTIVE" and p.stock_state != "in_stock"),
            }
        return HomeDTO(departments=departments, stats=stats, latest=latest,
                       seller_names=seller_display_names(p.seller_id for p in latest + recommended), shop=shop,
                       recommended=recommended)

    def admin_dashboard(self):
        products = self.products.list_all_products()
        departments, stats = self._summary([p for p in products if p.status == "ACTIVE"])
        accounts = None
        if StoredProcedures.available():  # RDS MySQL: consulta consolidada con sp_resumen_cuentas
            try:
                accounts = StoredProcedures.account_summary()
            except StoredProcedures.ProcedureMissing:
                pass  # falta ejecutar el script 06 en RDS: se cuenta con el ORM
        if accounts is None:  # SQLite (pruebas y modo local): el mismo conteo con el ORM
            accounts = {"usuarios": db.session.scalar(
                db.select(db.func.count()).select_from(User).where(User.status != "deleted")) or 0}
        admin_stats = {
            "users": accounts["usuarios"],
            "blocked": sum(1 for p in products if p.status == "BLOCKED"),
        }
        failures = db.session.scalars(
            db.select(AuthEvent).where(AuthEvent.event.in_(FAILED_LOGIN_EVENTS))
            .order_by(AuthEvent.created_at.desc()).limit(10)
        ).all()
        actions = db.session.scalars(
            db.select(AdminAction).order_by(AdminAction.created_at.desc()).limit(10)
        ).all()
        return AdminDashboardDTO(stats=stats, admin_stats=admin_stats, departments=departments,
                                 failures=failures, actions=actions)
