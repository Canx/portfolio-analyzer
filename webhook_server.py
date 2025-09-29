# webhook_server.py
import json
import stripe
from flask import Flask, request, Response
from src.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from src.auth import initialize_firebase_admin
from src.database import update_user_profile

# --- INICIALIZACIÓN ---
app = Flask(__name__)
stripe.api_key = STRIPE_SECRET_KEY

# Inicializamos la conexión de administrador a Firebase al arrancar el servidor
auth_admin, db_admin = initialize_firebase_admin()

if not db_admin:
    print("🔥 CRÍTICO: No se pudo inicializar la conexión de administrador a Firebase. El servidor no podrá actualizar la base de datos.")

print("✅ Servidor de webhooks iniciado.")
print(f"   Escuchando en http://localhost:4243/stripe-webhook")

# --- ENDPOINT DEL WEBHOOK ---
@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """
    Endpoint que recibe notificaciones de Stripe.
    Verifica la firma y procesa el evento.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    # 1. Verificar la firma del webhook
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Payload inválido
        print(f"⚠️ Error de payload: {e}")
        return Response(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Firma inválida
        print(f"⚠️ Error de firma: {e}")
        return Response(status=400)

    # 2. Manejar el evento
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')
        subscription_id = session.get('subscription')
        
        if client_reference_id and subscription_id:
            print(f"🔔 Pago exitoso para el usuario: {client_reference_id}, Suscripción: {subscription_id}")
            
            if db_admin:
                profile_update_data = {
                    "subscription_plan": "premium",
                    "stripe_subscription_id": subscription_id
                }
                success = update_user_profile(db_admin, client_reference_id, profile_update_data)
                if not success:
                    # Si falla, devolvemos un error 500 para que Stripe pueda reintentar.
                    return Response(status=500)
            else:
                print("🔥 ERROR: No hay conexión de administrador a la DB. No se puede actualizar el plan.")
                return Response(status=500)

        else:
            print("⚠️ Recibido 'checkout.session.completed' sin 'client_reference_id' o 'subscription'")

    else:
        print(f"Unhandled event type {event['type']}")

    return Response(status=200)

# --- EJECUCIÓN ---
if __name__ == '__main__':
    # Puerto estándar para webhooks de Stripe en desarrollo
    app.run(port=4243)
