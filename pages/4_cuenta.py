import streamlit as st
from src.auth import page_init_and_auth, logout_user

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()
    
# --- Contenido de la Página ---
st.title("⚙️ Mi Cuenta")

user_email = st.session_state.user_info.get("email", "N/A")
user_plan = st.session_state.user_info.get("subscription_plan", "free")

st.write(f"**Usuario:** {user_email}")
st.write(f"**Plan Actual:**", user_plan.capitalize())

st.markdown("---")

# --- Lógica de Planes y Mejoras ---
if user_plan == "free":
    st.subheader("🚀 ¡Pásate a Premium!")
    st.write("Accede a funcionalidades avanzadas como backtesting ilimitado y reportes en PDF.")
    
    # Este botón en el futuro redirigirá a una pasarela de pago como Stripe
    if st.button("Mejorar a Premium"):
        # Por ahora, simulamos la mejora para probar la lógica
        st.session_state.user_info["subscription_plan"] = "premium"
        
        # Guardamos el nuevo perfil en la base de datos
        from src.database import save_user_data
        
        # Preparamos los datos a guardar (solo el perfil)
        profile_data_to_save = {
            "subscription_plan": "premium",
            "carteras": st.session_state.get("carteras", {})
        }
        save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)
        
        st.success("¡Has mejorado tu plan a Premium! Refresca la página para ver los cambios.")
        st.balloons()
        st.rerun()
else:
    st.success("✅ Tienes un plan Premium. ¡Gracias por tu apoyo!")