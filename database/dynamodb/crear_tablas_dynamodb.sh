#!/usr/bin/env bash
# Crea las 4 tablas DynamoDB de la Parte 5 (mismos nombres, claves, índices, proyecciones y TTL)
# y carga el ítem de ejemplo de cada una (sección A.6 del documento).
#
# Uso en AWS CloudShell (región us-east-1):
#   1. Consola de AWS → icono >_ de la barra superior o el botón "CloudShell" de la barra inferior.
#   2. Acciones → Cargar archivo → este archivo.
#   3. bash crear_tablas_dynamodb.sh
#
# Si una tabla ya existe, el script se detiene en ese punto: bórrala desde la consola o
# comenta su bloque. Equivale exactamente a crearlas a mano con la consola (secciones A.1–A.6).
set -euo pipefail
export AWS_DEFAULT_REGION=us-east-1

echo "== Products =="
aws dynamodb create-table \
  --table-name Products \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=product_id,AttributeType=S \
      AttributeName=listed_category,AttributeType=S \
      AttributeName=price,AttributeType=N \
      AttributeName=seller_id,AttributeType=S \
  --key-schema AttributeName=product_id,KeyType=HASH \
  --global-secondary-indexes '[
    {"IndexName": "byCategoryPrice",
     "KeySchema": [{"AttributeName": "listed_category", "KeyType": "HASH"},
                   {"AttributeName": "price", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "INCLUDE",
                    "NonKeyAttributes": ["name", "search_name", "category", "stock", "seller_id",
                                         "condition", "cover_image", "rating_sum", "rating_count"]}},
    {"IndexName": "bySeller",
     "KeySchema": [{"AttributeName": "seller_id", "KeyType": "HASH"},
                   {"AttributeName": "product_id", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "INCLUDE",
                    "NonKeyAttributes": ["name", "price", "stock", "category", "status",
                                         "blocked_reason", "prior_status", "cover_image",
                                         "sales_count", "updated_at", "version", "seller_sku"]}}
  ]' > /dev/null

echo "== Orders =="
aws dynamodb create-table \
  --table-name Orders \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
      AttributeName=GSI1PK,AttributeType=S AttributeName=GSI1SK,AttributeType=S \
      AttributeName=GSI2PK,AttributeType=S AttributeName=GSI2SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[
    {"IndexName": "GSI1",
     "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}, {"AttributeName": "GSI1SK", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "ALL"}},
    {"IndexName": "GSI2",
     "KeySchema": [{"AttributeName": "GSI2PK", "KeyType": "HASH"}, {"AttributeName": "GSI2SK", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "ALL"}}
  ]' > /dev/null

echo "== Marketplace =="
aws dynamodb create-table \
  --table-name Marketplace \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE > /dev/null

echo "== Community =="
aws dynamodb create-table \
  --table-name Community \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
      AttributeName=GSI1PK,AttributeType=S AttributeName=GSI1SK,AttributeType=S \
      AttributeName=GSI2PK,AttributeType=S AttributeName=GSI2SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[
    {"IndexName": "GSI1",
     "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"}, {"AttributeName": "GSI1SK", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "ALL"}},
    {"IndexName": "GSI2",
     "KeySchema": [{"AttributeName": "GSI2PK", "KeyType": "HASH"}, {"AttributeName": "GSI2SK", "KeyType": "RANGE"}],
     "Projection": {"ProjectionType": "ALL"}}
  ]' > /dev/null

echo "Esperando a que las tablas estén activas..."
for t in Products Orders Marketplace Community; do
  aws dynamodb wait table-exists --table-name "$t"
done

echo "== TTL (expires_at) en Marketplace y Community =="
aws dynamodb update-time-to-live --table-name Marketplace \
  --time-to-live-specification "Enabled=true,AttributeName=expires_at" > /dev/null
aws dynamodb update-time-to-live --table-name Community \
  --time-to-live-specification "Enabled=true,AttributeName=expires_at" > /dev/null

echo "== Ítems de ejemplo (sección A.6) =="
aws dynamodb put-item --table-name Products --item '{
  "product_id": {"S": "PROD-00001"}, "name": {"S": "Wireless Mouse"},
  "search_name": {"S": "wireless mouse"}, "category": {"S": "computer-accessories"},
  "listed_category": {"S": "computer-accessories"}, "price": {"N": "499.00"},
  "stock": {"N": "25"}, "seller_id": {"S": "SEL-001"}, "condition": {"S": "NEW"},
  "status": {"S": "ACTIVE"}, "version": {"N": "1"}}'
aws dynamodb put-item --table-name Orders --item '{
  "PK": {"S": "ORDER#01JB8X5Q2M7R9T3VWZ4N6K1H0D"}, "SK": {"S": "ORDER"},
  "entity": {"S": "Order"}, "status": {"S": "PENDING_PAYMENT"}, "total": {"N": "499"},
  "GSI1PK": {"S": "USER#7f3c1a2e-5b4d-4c8a-9e21-3d6f0a7b8c90"},
  "GSI1SK": {"S": "ORDER#01JB8X5Q2M7R9T3VWZ4N6K1H0D"},
  "GSI2PK": {"S": "STATUS#PENDING_PAYMENT"},
  "GSI2SK": {"S": "2026-10-11T18:20:00Z#01JB8X5Q2M7R9T3VWZ4N6K1H0D"}}'
aws dynamodb put-item --table-name Marketplace --item '{
  "PK": {"S": "USER#7f3c1a2e-5b4d-4c8a-9e21-3d6f0a7b8c90"}, "SK": {"S": "CART#PROD-00001"},
  "entity": {"S": "CartItem"}, "quantity": {"N": "1"}, "quoted_price": {"N": "499"},
  "expires_at": {"N": "1794268800"}}'
aws dynamodb put-item --table-name Community --item '{
  "PK": {"S": "PRODUCT#PROD-00001"}, "SK": {"S": "REVIEW#01JC2Y6R3N8S4T5VWZ7P9K2H1D"},
  "entity": {"S": "Review"}, "rating": {"N": "5"}, "status": {"S": "VISIBLE"},
  "GSI1PK": {"S": "USER#7f3c1a2e-5b4d-4c8a-9e21-3d6f0a7b8c90"},
  "GSI1SK": {"S": "REVIEW#01JC2Y6R3N8S4T5VWZ7P9K2H1D"}}'

echo "== Verificación =="
aws dynamodb list-tables --output text
for t in Products Orders Marketplace Community; do
  aws dynamodb describe-table --table-name "$t" \
    --query "Table.[TableName, TableStatus, BillingModeSummary.BillingMode, length(GlobalSecondaryIndexes || \`[]\`)]" \
    --output text
done
echo "Listo. Esperado: Products 2 índices, Orders 2, Marketplace 0, Community 2; todas ACTIVE y PAY_PER_REQUEST."
