"""Pedidos y ventas: Flask → API Gateway → lambdaCreateOrder / lambdaListOrders /
lambdaGetOrder / lambdaUpdateOrderStatus / lambdaListSales → DynamoDB Orders.

- La dirección se busca en RDS con el user_id de la sesión (anti IDOR) y viaja como copia:
  si después la persona la edita, el pedido conserva a dónde se envió.
- Precios, existencias y carrito los lee la Lambda; del navegador solo llega el ID de la dirección.
- Tras comprar o cancelar, se vacía la caché del catálogo (cambiaron las existencias).
"""
from Implementation.SharedImplementation.ApiGatewayClient import actor_of, gateway
from Implementation.SharedImplementation.ShopPaths import order_path
from Interfaces.ApiErrors import NotFoundError
from Interfaces.OrderServiceInterface.IOrderService import IOrderService
from Interfaces.OrderServiceInterface.OrderDTO import ACTIONS, OrderDetailDTO, OrderSummaryDTO
from Security import security_log


class OrderServiceImplementation(IOrderService):
    def __init__(self, address_service, product_service):
        self.addresses = address_service
        self.products = product_service

    def checkout(self, user, address_id):
        address = self.addresses.shipping_copy(user, address_id)
        if address is None:
            security_log("idor_blocked", user=user.id, address=str(address_id)[:20], op="checkout")
            raise NotFoundError("Dirección no encontrada")
        body = gateway().request("POST", "/orders", json={"address": address}, actor=actor_of(user))
        self.products.invalidate_cache()
        return [OrderSummaryDTO.from_api(raw) for raw in body.get("pedidos") or []]

    def list_orders(self, user):
        body = gateway().request("GET", "/orders", actor=actor_of(user))
        return [OrderSummaryDTO.from_api(raw) for raw in body.get("pedidos") or []]

    def list_sales(self, user):
        body = gateway().request("GET", "/sales", actor=actor_of(user))
        return [OrderSummaryDTO.from_api(raw) for raw in body.get("ventas") or []]

    def get_order(self, user, order_id):
        body = gateway().request("GET", order_path(order_id), actor=actor_of(user))
        return OrderDetailDTO.from_api(body.get("pedido") or {})

    def change_status(self, user, order_id, action, reason=""):
        if action not in ACTIONS:
            raise NotFoundError("Acción inválida")
        payload = {"action": action}
        if reason:
            payload["reason"] = reason
        body = gateway().request("PUT", order_path(order_id), json=payload, actor=actor_of(user))
        if action == "cancel":
            self.products.invalidate_cache()
        return OrderDetailDTO.from_api(body.get("pedido") or {})
