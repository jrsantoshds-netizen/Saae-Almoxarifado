# =================================== IMPORTAÇÕES ==============================
import streamlit as st
import sqlite3
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import base64
from pathlib import Path
import os
import sys
import pandas as pd
from rembg import remove
from PIL import Image
import io
#=============================== MÓDULOS ==============================
import sys
from pathlib import Path
import plotly.express as px   # ← Import local de segurança (caso dê problema)


# ==================== CONFIGURAÇÃO DE PATH ====================
# Adiciona o diretório raiz e a pasta modulos ao path
BASE_DIR = Path(__file__).parent.resolve()
MODULOS_DIR = BASE_DIR / "modulos"

sys.path.insert(0, str(BASE_DIR))      # Diretório raiz
sys.path.insert(0, str(MODULOS_DIR))   # Pasta dos módulos


#=============================== IMPORTS PADRÃO ==============================

# Adicionar módulos ao path
#sys.path.insert(0, str(Path(__file__).parent / "modulos"))
from produtos import (
    criar_tabelas, cadastrar_produto, listar_produtos, obter_produto,
    atualizar_produto, excluir_produto, gerar_pdf_relatorio
)
from movimentacoes import (
    registrar_movimentacao, listar_movimentacoes, obter_movimentacao,
    gerar_recibo_pdf, gerar_relatorio_movimentacoes
)

# ====================== CONFIGURAÇÃO ======================
# Use caminho absoluto para o banco de dados
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "db.sqlite3"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )""")

    c.execute("""CREATE TABLE IF NOT EXISTS products (
                    id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_produto TEXT NOT NULL,
                    tipo_produto TEXT,
                    categoria_produto TEXT,
                    descricao TEXT,
                    estoque_minimo INTEGER DEFAULT 0,
                    estoque_atual INTEGER DEFAULT 0,
                    data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")

    c.execute("""CREATE TABLE IF NOT EXISTS movements (
                    id_mov INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_produto INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    quantidade INTEGER NOT NULL,
                    observacao TEXT,
                    usuario TEXT,
                    data_mov DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(id_produto) REFERENCES products(id_produto)
                )""")

    c.execute("""CREATE TABLE IF NOT EXISTS recibos (
                 id_recibo INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_recibo TEXT,
                produto TEXT,
                quantidade INTEGER,
                usuario TEXT,
                recebedor TEXT,
                observacao TEXT,
                data TEXT
                )""")

    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_random_password(length=10):
    characters = string.ascii_letters + string.digits + "!@#$%"
    return "".join(random.choice(characters) for _ in range(length))


# =================== INICIALIZAÇÃO DO BANCO E ESTADO =================
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""


# ====================== PLANO DE FUNDO LOCAL (BASE64) ======================
def set_background():
    # Usar caminho absoluto
    image_path = BASE_DIR / "images" / "fundo_saae.png"

    if not image_path.exists():
        st.warning(f"⚠️ Imagem de fundo não encontrada em: {image_path}")
        # Usar background padrão se não encontrar a imagem
        st.markdown(
            """
            <style>
                [data-testid="stAppViewContainer"] {
                    background-color: #1e3a5f;
                }
                .main .block-container {
                    background-color: rgba(0, 0, 0, 0.35);
                    border-radius: 15px;
                    padding: 25px;
                    margin-top: 10px;
                }
                h1, h2, h3, p, label, .stMarkdown, .stTextInput label, 
                .stSelectbox label, .stRadio label {
                    color: white !important;
                }
                .stButton button {
                    background-color: #00A3E0 !important;
                    color: white !important;
                    font-weight: bold !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        return

    # Converte a imagem para Base64
    try:
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode()

        st.markdown(
            f"""
            <style>
                [data-testid="stAppViewContainer"] {{
                    background-image: url("data:image/png;base64,{encoded_string}");
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }}
                
                [data-testid="stAppViewContainer"]::before {{
                    content: "";
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.75);
                    z-index: 0;
                }}

                .main .block-container {{
                    position: relative;
                    z-index: 1;
                    background-color: rgba(0, 0, 0, 0.35);
                    border-radius: 15px;
                    padding: 25px;
                    margin-top: 10px;
                }}

                h1, h2, h3, p, label, .stMarkdown, .stTextInput label, 
                .stSelectbox label, .stRadio label {{
                    color: white !important;
                    text-shadow: 2px 2px 10px rgba(0,0,0,0.95);
                }}

                .stButton button {{
                    background-color: #00A3E0 !important;
                    color: white !important;
                    font-weight: bold !important;
                    border-radius: 8px !important;
                }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"Erro ao carregar imagem: {e}")


# ====================== ENVIO DE EMAIL ======================
def send_reset_email(email, new_password):
    sender_email = os.environ.get("SENDER_EMAIL", "")
    sender_password = os.environ.get("SENDER_PASSWORD", "")

    if not sender_email or not sender_password:
        st.warning("⚠️ Email não configurado. Configure as variáveis SENDER_EMAIL e SENDER_PASSWORD.")
        return False

    subject = "🔑 Recuperação de Senha - SAAE Itacoatiara"
    body = f"""
    Olá,

    Você solicitou a recuperação de senha.
    
    Sua nova senha temporária é: **{new_password}**

    Recomendamos que você altere esta senha após fazer login.

    Atenciosamente,
    Departamento de TI - SAAE Itacoatiara
    """

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")
        return False


# ====================== FUNÇÕES DE USUÁRIO ======================
def register_user(username, email, password):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        hashed = hash_password(password)
        c.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username.strip(), email.strip().lower(), hashed),
        )
        conn.commit()
        return True, "✅ Cadastro realizado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Usuário ou email já cadastrado!"
    finally:
        conn.close()


def login_user(username, password):
    hashed = hash_password(password)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM users WHERE (username=? OR email=?) AND password=?",
        (username.strip(), username.strip().lower(), hashed),
    )
    user = c.fetchone()
    conn.close()
    return user is not None


def reset_password(email):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
    user = c.fetchone()

    if not user:
        conn.close()
        return False, "❌ Email não encontrado."

    new_pass = generate_random_password()
    hashed = hash_password(new_pass)

    c.execute(
        "UPDATE users SET password=? WHERE email=?", (hashed, email.strip().lower())
    )
    conn.commit()
    conn.close()

    if send_reset_email(email, new_pass):
        return True, f"✅ Nova senha enviada para **{email}**!"
    else:
        return False, "❌ Erro ao enviar email."


# ====================== APLICAR FUNDO ======================
set_background()

# ====================== INTERFACE ======================
if not st.session_state.logged_in:
    st.title("🔐  SAAE Itacoatiara")
    st.markdown("### Faça login para acessar o sistema interno")

    tab1, tab2, tab3 = st.tabs(["Entrar", "Cadastrar", "🔑 Esqueci minha senha"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("👤 Usuário ou Email")
            password = st.text_input("🔑 Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                if login_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(f"Bem-vindo, **{username}**!")
                    st.rerun()
                else:
                    st.error("Usuário/Email ou senha incorretos.")

    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("👤 Usuário")
            new_email = st.text_input("✉️ Email")
            new_pass = st.text_input("🔑 Senha", type="password")
            confirm_pass = st.text_input("🔁 Confirmar Senha", type="password")

            if st.form_submit_button("Cadastrar", type="secondary"):
                if not new_user or not new_email or not new_pass:
                    st.error("Todos os campos são obrigatórios.")
                elif new_pass != confirm_pass:
                    st.error("As senhas não coincidem!")
                elif len(new_pass) < 8:
                    st.error("Senha deve ter no mínimo 8 caracteres.")
                else:
                    success, msg = register_user(new_user, new_email, new_pass)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)

    with tab3:
        st.info("Digite seu email cadastrado para receber uma nova senha.")
        with st.form("reset_form"):
            reset_email = st.text_input("✉️ Seu Email")
            if st.form_submit_button("Enviar Nova Senha", type="primary"):
                if reset_email:
                    success, msg = reset_password(reset_email)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Digite seu email.")

    st.stop()  # ← Bloqueia completamente o resto da aplicação

# ====================== ÁREA LOGADA ======================
st.sidebar.success(f"👋 Logado como: **{st.session_state.username}**")

if st.sidebar.button("🚪 Sair", type="secondary"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()
# ==================== IMAGEM SEM FUNDO ====================
imagem = Image.open("fundo.png")
    
# Opção 1: Imagem da internet (URL)
st.image("fundo_news.png", width=900)

st.title(" Bem-vindo ao Sistema SAAE")
st.markdown("---")

# Menu de navegação
page = st.sidebar.radio(
    "🗂️ Navegação",
    ["📊 Dashboard", "📦 Cadastro de Produtos", "🔄 Entradas/saida"]
)

if page == "📊 Dashboard":
    st.header("📊 Dashboard")
    #st.info("Página em desenvolvimento - Dashboard com estatísticas")
#============

    #elif page == "📊 Dashboard":
    st.header("📊 Dashboard - Controle de Almoxarifado")
    st.markdown("### Visão geral do estoque SAAE Itacoatiara")

    # ==================== CARREGAR DADOS ====================
    produtos = listar_produtos()
    movimentacoes = listar_movimentacoes()

    if not produtos:
        st.warning("Nenhum produto cadastrado ainda.")
        st.stop()

    df_produtos = pd.DataFrame(produtos)
    df_mov = pd.DataFrame(movimentacoes)

    # ==================== KPIs PRINCIPAIS ====================
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📦 Total de Produtos",
            value=len(df_produtos),
            delta=None
        )

    with col2:
        estoque_total = df_produtos['estoque_atual'].sum()
        st.metric(
            label="📊 Itens em Estoque",
            value=f"{estoque_total:,}",
        )

    with col3:
        abaixo_minimo = len(df_produtos[df_produtos['estoque_atual'] < df_produtos['estoque_minimo']])
        st.metric(
            label="⚠️ Abaixo do Mínimo",
            value=abaixo_minimo,
            delta=abaixo_minimo,
            delta_color="inverse"
        )

    with col4:
        ultima_mov = df_mov['data_mov'].max() if not df_mov.empty else "Sem movimentações"
        st.metric(
            label="🕒 Última Movimentação",
            value=ultima_mov[:16] if isinstance(ultima_mov, str) else "—"
        )

    st.markdown("---")

    # ==================== GRÁFICOS ====================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Distribuição por Tipo")
        if not df_produtos.empty:
            tipo_count = df_produtos['tipo_produto'].value_counts()
            fig1 = px.pie(
                names=tipo_count.index,
                values=tipo_count.values,
                title="Produtos por Tipo",
                color_discrete_sequence=px.colors.sequential.Blues
            )
            st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader("📈 Estoque por Categoria")
        if not df_produtos.empty:
            cat_estoque = df_produtos.groupby('categoria_produto')['estoque_atual'].sum()
            fig2 = px.bar(
                x=cat_estoque.index,
                y=cat_estoque.values,
                labels={'x': 'Categoria', 'y': 'Quantidade em Estoque'},
                color=cat_estoque.values,
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ==================== ALERTAS DE ESTOQUE BAIXO ====================
    st.subheader("⚠️ Produtos com Estoque Crítico")
    criticos = df_produtos[df_produtos['estoque_atual'] < df_produtos['estoque_minimo']].copy()

    if criticos.empty:
        st.success("✅ Todos os produtos estão acima do estoque mínimo!")
    else:
        criticos['Deficit'] = criticos['estoque_minimo'] - criticos['estoque_atual']
        st.dataframe(
            criticos[['nome_produto', 'tipo_produto', 'estoque_atual', 'estoque_minimo', 'Deficit']],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    # ==================== ÚLTIMAS MOVIMENTAÇÕES ====================
    st.subheader("🔄 Últimas 10 Movimentações")

    if not df_mov.empty:
        ultimas = df_mov.sort_values('data_mov', ascending=False).head(10)
        
        ultimas_display = ultimas.copy()
        ultimas_display['Data'] = pd.to_datetime(ultimas_display['data_mov']).dt.strftime("%d/%m/%Y %H:%M")
        
        st.dataframe(
            ultimas_display[['Data', 'tipo_mov', 'nome_produto', 'quantidade', 'usuario', 'numero_recibo']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "tipo_mov": "Tipo",
                "nome_produto": "Produto",
                "quantidade": "Qtd",
                "usuario": "Responsável"
            }
        )
    else:
        st.info("Nenhuma movimentação registrada ainda.")

    # ==================== BOTÕES RÁPIDOS ====================
    st.markdown("---")
    st.subheader("Ações Rápidas")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("➕ Novo Produto", use_container_width=True):
            st.switch_page("pages/2_📦_Cadastro_de_Produtos.py")  # ou mudar para o seu sistema de navegação

    with col2:
        if st.button("🔄 Registrar Movimentação", use_container_width=True):
            st.switch_page("pages/3_🔄_Entradas_saida.py")

    with col3:
        if st.button("📄 Gerar Relatório Completo", use_container_width=True):
            pdf_buffer = gerar_pdf_relatorio(produtos)
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=pdf_buffer,
                file_name=f"relatorio_completo_{pd.Timestamp.now().strftime('%d_%m_%Y')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )





    #=======
elif page == "📦 Cadastro de Produtos":
    st.header("📦 Cadastramento de Produtos")
    st.markdown("---")
    
    # Inicializar tabelas
    criar_tabelas()
    
    # Abas
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "➕ Cadastro",
        "✏️ Editar",
        "🗑️ Excluir",
        "🔍 Consulta",
        "📄 Relatório PDF"
    ])
    
    # ==================== ABA 1: CADASTRO ====================
    with tab1:
        st.subheader("➕ Cadastrar Novo Produto")
        
        tipos = [" ","Hidraulico", "Eletrico", "Informática"]
        categorias = [" ","PC", "MT", "UND", "CX", "DZ", "LT", "KG"]
        
        with st.form("form_cadastro"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("📝 Nome do Produto *", placeholder="Ex: Cloro em Pó")
                tipo = st.selectbox("🏷️ Tipo", tipos)
                estoque_minimo = st.number_input("📦 Estoque Mínimo", min_value=0, value=10)
            
            with col2:
                categoria = st.selectbox("📂 Categoria", categorias)
                estoque_atual = st.number_input("📦 Estoque Atual", min_value=0, value=0)
            
            descricao = st.text_area("📖 Descrição", placeholder="Detalhes do produto...")
            
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                submit = st.form_submit_button("✅ Cadastrar", type="primary", use_container_width=True)
            
            with col2:
                st.form_submit_button("🔄 Limpar", type="secondary", use_container_width=True)
            
            if submit:
                if not nome:
                    st.error("❌ Nome do produto é obrigatório!")
                else:
                    success, msg = cadastrar_produto(
                        nome, tipo, categoria, descricao, 
                        estoque_minimo, estoque_atual
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    
    # ==================== ABA 2: EDITAR ====================
    with tab2:
        st.subheader("✏️ Editar Produto")
        
        produtos = listar_produtos()
        tipos = [" ","Hidraulico", "Eletrico", "Informática", "Outros"]
        categorias = [" ","PC", "MT", "UND", "CX", "DZ", "LT", "KG"]
        
        if not produtos:
            st.warning("⚠️ Nenhum produto cadastrado ainda.")
        else:
            # Seletor de produto
            produto_selecionado = st.selectbox(
                "🔍 Selecione um produto para editar:",
                options=[p['id_produto'] for p in produtos],
                format_func=lambda x: next((p['nome_produto'] for p in produtos if p['id_produto'] == x), ""),
                key="select_editar"
            )
            
            if produto_selecionado:
                produto = obter_produto(produto_selecionado)
                
                if produto:
                    st.info(f"Editando: **{produto['nome_produto']}** (ID: {produto['id_produto']})")
                    
                    with st.form("form_editar"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            nome = st.text_input("📝 Nome do Produto", value=produto['nome_produto'])
                            tipo = st.selectbox("🏷️ Tipo", tipos, index=tipos.index(produto['tipo_produto']) if produto['tipo_produto'] in tipos else 0)
                            estoque_minimo = st.number_input("📦 Estoque Mínimo", value=int(produto['estoque_minimo']))
                        
                        with col2:
                            categoria = st.selectbox("📂 Categoria", categorias, index=categorias.index(produto['categoria_produto']) if produto['categoria_produto'] in categorias else 0)
                            estoque_atual = st.number_input("📦 Estoque Atual", value=int(produto['estoque_atual']))
                        
                        descricao = st.text_area("📖 Descrição", value=produto['descricao'] or "")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            submit = st.form_submit_button("✅ Salvar Alterações", type="primary", use_container_width=True)
                        
                        if submit:
                            success, msg = atualizar_produto(
                                produto_selecionado, nome, tipo, categoria, 
                                descricao, estoque_minimo, estoque_atual
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
    
    # ==================== ABA 3: EXCLUIR ====================
    with tab3:
        st.subheader("🗑️ Excluir Produto")
        
        produtos = listar_produtos()
        
        if not produtos:
            st.warning("⚠️ Nenhum produto cadastrado.")
        else:
            # Seletor de produto
            produto_selecionado = st.selectbox(
                "🔍 Selecione um produto para excluir:",
                options=[p['id_produto'] for p in produtos],
                format_func=lambda x: next((p['nome_produto'] for p in produtos if p['id_produto'] == x), ""),
                key="select_excluir"
            )
            
            if produto_selecionado:
                produto = obter_produto(produto_selecionado)
                
                if produto:
                    st.warning(f"⚠️ Você está prestes a excluir: **{produto['nome_produto']}**")
                    st.info(f"ID: {produto['id_produto']} | Estoque: {produto['estoque_atual']} | Tipo: {produto['tipo_produto']}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🗑️ Confirmar Exclusão", type="primary", use_container_width=True):
                            success, msg = excluir_produto(produto_selecionado)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with col2:
                        st.button("❌ Cancelar", type="secondary", use_container_width=True)
    
    # ==================== ABA 4: CONSULTA ====================
    with tab4:
        st.subheader("🔍 Consulta de Produtos")
        
        produtos = listar_produtos()
        
        if not produtos:
            st.info("ℹ️ Nenhum produto cadastrado ainda.")
        else:
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                filtro_nome = st.text_input("🔍 Filtrar por nome", "")
            
            with col2:
                tipos = ["Todos"] + list(set([p['tipo_produto'] for p in produtos if p['tipo_produto']]))
                filtro_tipo = st.selectbox("Tipo", tipos)
            
            with col3:
                categorias = ["Todas"] + list(set([p['categoria_produto'] for p in produtos if p['categoria_produto']]))
                filtro_categoria = st.selectbox("Categoria", categorias)
            
            # Aplicar filtros
            produtos_filtrados = produtos
            
            if filtro_nome:
                produtos_filtrados = [p for p in produtos_filtrados 
                                     if filtro_nome.lower() in p['nome_produto'].lower()]
            
            if filtro_tipo != "Todos":
                produtos_filtrados = [p for p in produtos_filtrados if p['tipo_produto'] == filtro_tipo]
            
            if filtro_categoria != "Todas":
                produtos_filtrados = [p for p in produtos_filtrados if p['categoria_produto'] == filtro_categoria]
            
            # Estatísticas
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📦 Total de Produtos", len(produtos_filtrados))
            
            with col2:
                abaixo_minimo = len([p for p in produtos_filtrados if p.get('estoque_atual', 0) < p.get('estoque_minimo', 0)])
                st.metric("⚠️ Abaixo do Mínimo", abaixo_minimo)
            
            with col3:
                estoque_total = sum([p.get('estoque_atual', 0) for p in produtos_filtrados])
                st.metric("📊 Estoque Total", estoque_total)
            
            st.markdown("---")
            
            # Tabela
            if produtos_filtrados:
                df = pd.DataFrame([{
                    'ID': p['id_produto'],
                    'Nome': p['nome_produto'],
                    'Tipo': p['tipo_produto'] or '-',
                    'Categoria': p['categoria_produto'] or '-',
                    'Estoque': p['estoque_atual'],
                    'Mínimo': p['estoque_minimo']
                } for p in produtos_filtrados])
                
                st.dataframe(df, use_container_width=True)
            else:
                st.info("ℹ️ Nenhum produto encontrado com os filtros aplicados.")
    
    # ==================== ABA 5: RELATÓRIO PDF ====================
    with tab5:
        st.subheader("📄 Relatório de Produtos em PDF")
        
        produtos = listar_produtos()
        
        if not produtos:
            st.info("ℹ️ Nenhum produto para gerar relatório.")
        else:
            # Opções de filtro para relatório
            st.markdown("**Opções de Relatório:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                relatorio_completo = st.checkbox("📋 Relatório Completo (Todos os produtos)", value=True)
            
            with col2:
                abaixo_minimo = st.checkbox("⚠️ Apenas produtos abaixo do estoque mínimo")
            
            if abaixo_minimo:
                produtos_relatorio = [p for p in produtos if p['estoque_atual'] < p['estoque_minimo']]
            else:
                produtos_relatorio = produtos
            
            st.info(f"📊 Produtos no relatório: {len(produtos_relatorio)}")
            
            # Gerar PDF
            if st.button("📥 Gerar PDF", type="primary", use_container_width=True):
                with st.spinner("Gerando PDF..."):
                    pdf_buffer = gerar_pdf_relatorio(produtos_relatorio)
                    
                    st.download_button(
                        label="⬇️ Baixar Relatório PDF",
                        data=pdf_buffer,
                        file_name=f"relatorio_produtos_{pd.Timestamp.now().strftime('%d_%m_%Y_%H_%M_%S')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
                    st.success("✅ PDF gerado com sucesso!")
            
            st.markdown("---")
            st.markdown("**Prévia dos Dados:**")
            
            df_preview = pd.DataFrame([{
                'ID': p['id_produto'],
                'Nome': p['nome_produto'],
                'Tipo': p['tipo_produto'] or '-',
                'Categoria': p['categoria_produto'] or '-',
                'Estoque': p['estoque_atual']
            } for p in produtos_relatorio])
            
            st.dataframe(df_preview, use_container_width=True)
    
    
elif page == "📦 Estoque":
    st.header("📦 Controle de Estoque")
    st.info("Página em desenvolvimento - Gestão de estoque")

elif page == "🔄 Entradas/saida":
    st.header("🔄 Entrada e Saida de Produtos")
    st.markdown("---")
    
    # Abas
    tab1, tab2, tab3 = st.tabs([
        "➕ Registrar Movimentação",
        "📋 Histórico",
        "📄 Relatório"
    ])
    
    # ==================== ABA 1: REGISTRAR MOVIMENTAÇÃO ====================
    with tab1:
        st.subheader("➕ Registrar Entrada/Saída de Produto")
        
        produtos = listar_produtos()
        
        if not produtos:
            st.warning("⚠️ Nenhum produto cadastrado. Cadastre produtos primeiro.")
        else:
            with st.form("form_movimentacao"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Seletor de produto
                    produto_id = st.selectbox(
                        "🔍 Selecione o Produto *",
                        options=[p['id_produto'] for p in produtos],
                        format_func=lambda x: next((p['nome_produto'] for p in produtos if p['id_produto'] == x), "")
                    )
                    
                    # Tipo de movimentação
                    tipo_mov = st.radio(
                        "📥 Tipo de Movimentação *",
                        options=["Entrada", "Saída"],
                        horizontal=True
                    )
                    
                    quantidade = st.number_input("📦 Quantidade *", min_value=1, value=1)
                
                with col2:
                    usuario = st.text_input("👤 Responsável (Seu Nome) *", value=st.session_state.username)
                    recebedor = st.text_input("👥 Recebedor/Entregador", placeholder="Nome de quem recebeu")
                    observacao = st.text_area("📝 Observação", placeholder="Detalhes adicionais...")
                
                # Obter produto para cálculo
                produto = obter_produto(produto_id)
                
                if produto:
                    st.info(f"📦 Estoque Atual: **{produto['estoque_atual']}** | Estoque Mínimo: **{produto['estoque_minimo']}**")
                    
                    # Calcular novo estoque
                    estoque_anterior = produto['estoque_atual']
                    if tipo_mov == "Entrada":
                        estoque_novo = estoque_anterior + quantidade
                    else:
                        if quantidade > estoque_anterior:
                            st.error(f"❌ Quantidade insuficiente! Disponível: {estoque_anterior}")
                            estoque_novo = estoque_anterior
                        else:
                            estoque_novo = estoque_anterior - quantidade
                    
                    st.warning(f"Novo Estoque: **{estoque_novo}**")
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    submit = st.form_submit_button("✅ Registrar", type="primary", use_container_width=True)
                
                with col2:
                    st.form_submit_button("🔄 Limpar", type="secondary", use_container_width=True)
                
                if submit:
                    if not usuario:
                        st.error("❌ Nome do responsável é obrigatório!")
                    elif tipo_mov == "Saída" and quantidade > estoque_anterior:
                        st.error(f"❌ Quantidade insuficiente! Disponível: {estoque_anterior}")
                    else:
                        # Registrar movimentação
                        success, numero_recibo, msg = registrar_movimentacao(
                            produto_id, produto['nome_produto'], tipo_mov, quantidade,
                            observacao, usuario, recebedor, estoque_anterior, estoque_novo
                        )
                        
                        if success:
                            # Atualizar estoque do produto
                            atualizar_produto(
                                produto_id, produto['nome_produto'], 
                                produto['tipo_produto'], produto['categoria_produto'],
                                produto['descricao'], produto['estoque_minimo'], 
                                estoque_novo
                            )
                            
                            st.success(msg)
                            st.info(f"Número do Recibo: **{numero_recibo}**")
                            
                            # Gerar recibo automaticamente
                            col1, col2 = st.columns(2)
                            with col1:
                                mov_data = obter_movimentacao(
                                    listar_movimentacoes()[0]['id_mov'] if listar_movimentacoes() else None
                                )
                                if mov_data:
                                    pdf_buffer = gerar_recibo_pdf(mov_data)
                                    st.download_button(
                                        label="📥 Baixar Recibo",
                                        data=pdf_buffer,
                                        file_name=f"recibo_{numero_recibo}.pdf",
                                        mime="application/pdf",
                                        type="primary"
                                    )
                            
                            st.rerun()
                        else:
                            st.error(msg)
    
    # ==================== ABA 2: HISTÓRICO ====================
    with tab2:
        st.subheader("📋 Histórico de Movimentações")
        
        movimentacoes = listar_movimentacoes()
        
        if not movimentacoes:
            st.info("ℹ️ Nenhuma movimentação registrada.")
        else:
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                filtro_tipo = st.selectbox(
                    "Filtrar por Tipo",
                    ["Todas", "Entrada", "Saída"]
                )
            
            with col2:
                filtro_usuario = st.text_input("Filtrar por Responsável", "")
            
            with col3:
                filtro_produto = st.text_input("Filtrar por Produto", "")
            
            # Aplicar filtros
            movimentacoes_filtradas = movimentacoes
            
            if filtro_tipo != "Todas":
                movimentacoes_filtradas = [m for m in movimentacoes_filtradas if m['tipo_mov'] == filtro_tipo]
            
            if filtro_usuario:
                movimentacoes_filtradas = [m for m in movimentacoes_filtradas if filtro_usuario.lower() in (m['usuario'] or '').lower()]
            
            if filtro_produto:
                movimentacoes_filtradas = [m for m in movimentacoes_filtradas if filtro_produto.lower() in m['nome_produto'].lower()]
            
            st.markdown("---")
            st.info(f"📊 Total de registros: {len(movimentacoes_filtradas)}")
            
            # Tabela
            if movimentacoes_filtradas:
                df = pd.DataFrame([{
                    'Recibo': m['numero_recibo'],
                    'Data': pd.to_datetime(m['data_mov']).strftime("%d/%m/%Y %H:%M"),
                    'Tipo': m['tipo_mov'],
                    'Produto': m['nome_produto'],
                    'Quantidade': m['quantidade'],
                    'Est. Anterior': m['estoque_anterior'],
                    'Est. Novo': m['estoque_novo'],
                    'Responsável': m['usuario'] or '-',
                    'Recebedor': m['recebedor'] or '-'
                } for m in movimentacoes_filtradas])
                
                st.dataframe(df, use_container_width=True)
                
                # Opção para ver detalhes
                st.markdown("---")
                recibo_selecionado = st.selectbox(
                    "🔍 Ver detalhes do recibo:",
                    options=[m['numero_recibo'] for m in movimentacoes_filtradas],
                    key="select_recibo"
                )
                
                if recibo_selecionado:
                    mov = next((m for m in movimentacoes_filtradas if m['numero_recibo'] == recibo_selecionado), None)
                    if mov:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Nº Recibo:** {mov['numero_recibo']}")
                            st.write(f"**Produto:** {mov['nome_produto']}")
                            st.write(f"**Tipo:** {mov['tipo_mov']}")
                            st.write(f"**Quantidade:** {mov['quantidade']}")
                        
                        with col2:
                            st.write(f"**Responsável:** {mov['usuario'] or '-'}")
                            st.write(f"**Recebedor:** {mov['recebedor'] or '-'}")
                            st.write(f"**Estoque Anterior:** {mov['estoque_anterior']}")
                            st.write(f"**Estoque Novo:** {mov['estoque_novo']}")
                        
                        if mov['observacao']:
                            st.write(f"**Observação:** {mov['observacao']}")
                        
                        # Botão para baixar recibo
                        pdf_buffer = gerar_recibo_pdf(mov)
                        st.download_button(
                            label="📥 Baixar Recibo",
                            data=pdf_buffer,
                            file_name=f"recibo_{mov['numero_recibo']}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
            else:
                st.info("ℹ️ Nenhuma movimentação encontrada com os filtros aplicados.")
    
    # ==================== ABA 3: RELATÓRIO ====================
    with tab3:
        st.subheader("📄 Relatório de Movimentações em PDF")
        
        movimentacoes = listar_movimentacoes()
        
        if not movimentacoes:
            st.info("ℹ️ Nenhuma movimentação para gerar relatório.")
        else:
            st.markdown("**Opções de Relatório:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                start_date = st.date_input("📅 Data Inicial", value=pd.Timestamp.now() - pd.Timedelta(days=30))
            
            with col2:
                end_date = st.date_input("📅 Data Final", value=pd.Timestamp.now())
            
            col3, col4 = st.columns(2)
            
            with col3:
                relatorio_entrada = st.checkbox("📥 Incluir Entradas", value=True)
            
            with col4:
                relatorio_saida = st.checkbox("📤 Incluir Saídas", value=True)
            
            # Filtrar movimentações por tipo
            movimentacoes_relatorio = movimentacoes
            
            tipos_selecionados = []
            if relatorio_entrada:
                tipos_selecionados.append("Entrada")
            if relatorio_saida:
                tipos_selecionados.append("Saída")
            
            if tipos_selecionados:
                movimentacoes_relatorio = [m for m in movimentacoes if m['tipo_mov'] in tipos_selecionados]
            else:
                movimentacoes_relatorio = []
            
            # Filtrar por período
            movimentacoes_relatorio = [m for m in movimentacoes_relatorio 
                                     if start_date <= pd.to_datetime(m['data_mov']).date() <= end_date]
            
            st.info(f"📊 Movimentações no relatório: {len(movimentacoes_relatorio)}")
            
            # Gerar PDF
            if st.button("📥 Gerar PDF", type="primary", use_container_width=True):
                with st.spinner("Gerando PDF..."):
                    pdf_buffer = gerar_relatorio_movimentacoes(movimentacoes_relatorio)
                    
                    st.download_button(
                        label="⬇️ Baixar Relatório PDF",
                        data=pdf_buffer,
                        file_name=f"relatorio_movimentacoes_{pd.Timestamp.now().strftime('%d_%m_%Y_%H_%M_%S')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
                    st.success("✅ PDF gerado com sucesso!")
            
            st.markdown("---")
            st.markdown("**Prévia dos Dados:**")
            
            df_preview = pd.DataFrame([{
                'Data': pd.to_datetime(m['data_mov']).strftime("%d/%m/%Y %H:%M"),
                'Tipo': m['tipo_mov'],
                'Produto': m['nome_produto'],
                'Quantidade': m['quantidade'],
                'Responsável': m['usuario'] or '-'
            } for m in movimentacoes_relatorio])
            
            st.dataframe(df_preview, use_container_width=True)

elif page == "📋 Recibos":
    st.header("📋 Recibos")
    st.info("Página em desenvolvimento - Gestão de recibos")

