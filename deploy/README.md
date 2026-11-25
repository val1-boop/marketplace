# Publicar la demostración (sin AWS de Valeria)

La demostración usa datos de ejemplo en memoria. Se publica en una instancia **EC2** con **Docker** y
**Caddy** (HTTPS automático). Los nombres de los menús de AWS pueden cambiar; si algo no coincide, busca el
equivalente.

> Es una **demostración pública con datos de ejemplo**: no se conecta a RDS ni a DynamoDB reales y sus datos
> se borran cada vez que se reinicia. La versión conectada a AWS se muestra en local.

## 0. Antes de empezar
1. En **Billing → Budgets** crea un presupuesto con la plantilla **Zero spend budget** (aviso por correo ante
   cualquier cobro).
2. Crea un subdominio gratis en **duckdns.org** (por ejemplo `marketplace-demo.duckdns.org`). Todavía no pongas
   la IP.

## 1. Crear la instancia
1. AWS → **EC2 → Launch instance**.
2. Nombre `marketplace-demo`. Imagen: **Ubuntu Server 24.04 LTS**. Tipo: uno marcado **Free tier eligible**
   (t2.micro o t3.micro).
3. **Key pair:** puedes continuar sin llave si usarás *EC2 Instance Connect* (botón *Connect* en el navegador).
4. **Network settings → Edit:** marca **Allow HTTP** y **Allow HTTPS traffic from the internet**. La regla de
   SSH depende de cómo te vas a conectar:
   - **Botón *Connect* del navegador (EC2 Instance Connect):** en la regla de SSH usa *Source type* **Custom** y
     elige la lista de prefijos `com.amazonaws.us-east-1.ec2-instance-connect` (cambia `us-east-1` si usas otra
     región). **No** uses *My IP*: esa conexión sale de los servidores de AWS y no de tu computadora, así que
     con *My IP* el navegador no logra conectarse. Ver
     [Prerequisites for EC2 Instance Connect](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-connect-prerequisites.html).
   - **SSH desde tu terminal:** crea un *key pair* (archivo `.pem`, guárdalo fuera del repositorio), deja SSH
     solo desde **My IP** y conéctate con `ssh -i tu-llave.pem ubuntu@LA_IP`.
5. **Storage:** 8 GB. Pulsa **Launch instance**.
6. **EC2 → Elastic IPs → Allocate → Associate** con la instancia (IP fija). Apunta esa IP.
7. En duckdns.org pon esa IP en tu subdominio y pulsa *update*.

## 2. Instalar y arrancar
Conéctate (EC2 → tu instancia → **Connect → EC2 Instance Connect**) y ejecuta:

```bash
sudo apt update && sudo apt install -y git docker.io
sudo systemctl enable --now docker
git clone https://github.com/val1-boop/marketplace.git
cd marketplace
sudo docker build -t marketplace-demo .
sudo docker run -d --name demo --restart unless-stopped --network host \
  -e SESSION_COOKIE_SECURE=true -e TRUSTED_PROXY_COUNT=1 \
  -e ALLOWED_HOSTS=tu-subdominio.duckdns.org marketplace-demo
sudo docker logs demo      # aquí aparecen las cuentas de prueba y sus contraseñas
```

> Si el Pull Request con el `Dockerfile` y `tools/demo_wsgi.py` todavía no se fusionó en `main`, clona su rama:
> `git clone -b feature/luis-despliegue https://github.com/val1-boop/marketplace.git`.

## 3. HTTPS con Caddy
Instala Caddy siguiendo la guía oficial para Ubuntu (caddyserver.com/docs/install), copia
`deploy/Caddyfile.example` a `/etc/caddy/Caddyfile` cambiando el dominio y recarga:

```bash
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile      # pon tu subdominio real
sudo systemctl reload caddy
```
Abre `https://tu-subdominio.duckdns.org` en el navegador.

## 4. Al terminar
- `sudo docker rm -f demo` y **termina la instancia** (EC2 → Instance state → Terminate).
- **Libera la Elastic IP** (EC2 → Elastic IPs → Release) para que no cobre.

## Seguridad
- La demostración **no** tiene datos reales: no registres contraseñas que uses en otros sitios.
- Solo se abren los puertos 80 y 443 al público; SSH queda limitado como se explica en el paso 1.4.
- Cualquiera con la URL puede registrarse: apaga la instancia cuando termine la revisión.
