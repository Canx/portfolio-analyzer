import streamlit as st
import stripe
import streamlit.components.v1 as components
from streamlit_local_storage import LocalStorage
from src.auth import page_init_and_auth, logout_user
from src.database import save_user_data
from src.config import STRIPE_PRICE_ID, STRIPE_SECRET_KEY

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"Usuario: {st.session_state.user_info.get('email')}")
    if st.button("Cerrar Sesión"):
        localS = LocalStorage()
        logout_user(localS)
        st.rerun()

# --- Configuración de Stripe ---
stripe.api_key = STRIPE_SECRET_KEY

# --- Contenido de la Página ---
st.title("⚙️ Mi Cuenta")

user_email = st.session_state.user_info.get("email", "N/A")
user_id = st.session_state.user_info.get("localId", "") # ID de usuario de Firebase
user_plan = st.session_state.user_info.get("subscription_plan", "free")

st.write(f"**Usuario:** {user_email}")
st.write(f"**Plan Actual:** {user_plan.capitalize()}")

st.markdown("---")

st.subheader("🔑 Gestión de la Cuenta")
if st.button("Cambiar Contraseña"):
    try:
        auth.send_password_reset_email(user_email)
        st.success(f"✅ Se ha enviado un email a {user_email} con las instrucciones para cambiar tu contraseña.")
    except Exception as e:
        st.error(f"Error al enviar el email: {e}")

st.markdown("---")

# --- Lógica de Planes y Mejoras ---
if user_plan == "free":
    st.subheader("🚀 ¡Pásate a Premium!")
    st.write("Accede a funcionalidades avanzadas como la optimización de carteras y análisis detallados.")

    if st.button("Mejorar a Premium"):
        try:
            # URL base de tu aplicación. ¡IMPORTANTE: Cámbiala por tu URL en producción!
            base_url = "http://localhost:8501"
            
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price': STRIPE_PRICE_ID,
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                success_url=f'{base_url}/Mi_Cuenta?payment=success',
                cancel_url=f'{base_url}/Mi_Cuenta?payment=cancel',
                client_reference_id=user_id, # Enviamos el ID del usuario a Stripe
            )
            
            # Redirigir al usuario a la página de pago de Stripe
            redirect_url = checkout_session.url
            components.html(f'<meta http-equiv="refresh" content="0; url={redirect_url}"> ', height=0)
            st.info("Redirigiendo a la pasarela de pago...")

        except Exception as e:
            st.error(f"Error al contactar con la pasarela de pago: {e}")

else:
    st.success("✅ Tienes un plan Premium. ¡Gracias por tu apoyo!")

    st.subheader("💔 Cancelar Suscripción")
    st.warning("Si cancelas, perderás el acceso a las funcionalidades premium al final de tu periodo de facturación actual, pero tus datos no se verán afectados.")
    
    if st.button("Cancelar Plan Premium"):
        subscription_id = st.session_state.user_info.get("stripe_subscription_id")
        if not subscription_id:
            st.error("No se encontró el ID de tu suscripción. Por favor, contacta con soporte.")
        else:
            try:
                # Cancelar la suscripción en Stripe al final del periodo de facturación
                stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)

                # Actualizamos el perfil local para reflejar que la cancelación está pendiente
                st.session_state.user_info["subscription_plan"] = "premium_cancel_pending"
                
                # Guardamos el nuevo estado en la base de datos
                profile_data_to_save = {
                    "subscription_plan": "premium_cancel_pending",
                    "stripe_subscription_id": st.session_state.user_info.get("stripe_subscription_id"),
                    "carteras": st.session_state.get("carteras", {})
                }
                save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)

                st.success("Tu suscripción premium ha sido programada para ser cancelada. Seguirás teniendo acceso hasta el final de tu ciclo de facturación.")
                st.rerun()

            except Exception as e:
                st.error(f"Ocurrió un error al cancelar tu suscripción: {e}")
                st.info("Por favor, inténtalo de nuevo o contacta con soporte si el problema persiste.")

# --- Manejar respuestas de la pasarela de pago ---
if 'payment' in st.query_params:
    if st.query_params['payment'] == 'success':
        st.success("¡Pago completado con éxito! Tu plan se actualizará en breve. Refresca la página en unos momentos.")
        st.balloons()
    elif st.query_params['payment'] == 'cancel':
        st.warning("El proceso de pago fue cancelado. Tu plan no ha cambiado.")