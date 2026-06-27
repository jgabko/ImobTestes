import pandas as pd
import numpy as np
import ast
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, MultiLabelBinarizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ==========================================
# 1. Carregar os dados
# ==========================================
print("Carregando os dados...")
df = pd.read_csv('/home/JGMK/Documents/ImobTestes/ML_IMOB_CWB/imoveis_limpos.csv')
linhas_originais = df.shape[0]

# ==========================================
# 2. Remoção de Outliers (Tratamento do Item 2)
# ==========================================
print("Removendo outliers extremos de preço e metragem...")
# Limpeza por IQR para Preço
q1_preco, q3_preco = df['preco'].quantile(0.25), df['preco'].quantile(0.75)
iqr_preco = q3_preco - q1_preco
limite_sup_preco = q3_preco + 1.5 * iqr_preco
limite_inf_preco = max(0, q1_preco - 1.5 * iqr_preco)

# Limpeza por IQR para Metragem
q1_meta, q3_meta = df['metragem'].quantile(0.25), df['metragem'].quantile(0.75)
iqr_meta = q3_meta - q1_meta
limite_sup_meta = q3_meta + 1.5 * iqr_meta
limite_inf_meta = max(10, q1_meta - 1.5 * iqr_meta)

# Aplicando os filtros
df_filtrado = df[
    (df['preco'] >= limite_inf_preco) & (df['preco'] <= limite_sup_preco) &
    (df['metragem'] >= limite_inf_meta) & (df['metragem'] <= limite_sup_meta)
].copy()

linhas_filtradas = df_filtrado.shape[0]
print(f"-> Foram removidos {linhas_originais - linhas_filtradas} registros considerados outliers.")

# ==========================================
# 3. Engenharia de Features (Tratamento do Item 1)
# ==========================================
print("Processando listas de características textuais em colunas binárias...")

def converter_para_lista(texto):
    """Trata strings nulas ou mal formatadas e converte para listas reais do Python"""
    if pd.isna(texto) or not isinstance(texto, str):
        return []
    try:
        return ast.literal_eval(texto)
    except:
        return []

# Tratando as colunas textuais
df_filtrado['caracteristicas_imovel'] = df_filtrado['caracteristicas_imovel'].apply(converter_para_lista)
df_filtrado['caracteristicas_condominio'] = df_filtrado['caracteristicas_condominio'].apply(converter_para_lista)

# Transformando características do Imóvel em colunas 0 e 1
mlb_imovel = MultiLabelBinarizer()
imovel_dummies = pd.DataFrame(
    mlb_imovel.fit_transform(df_filtrado['caracteristicas_imovel']),
    columns=[f"imovel_{c.lower().replace(' ', '_')}" for c in mlb_imovel.classes_],
    index=df_filtrado.index
)

# Transformando características do Condomínio em colunas 0 e 1
mlb_condo = MultiLabelBinarizer()
condo_dummies = pd.DataFrame(
    mlb_condo.fit_transform(df_filtrado['caracteristicas_condominio']),
    columns=[f"condo_{c.lower().replace(' ', '_')}" for c in mlb_condo.classes_],
    index=df_filtrado.index
)

# Combinando tudo de volta no DataFrame final de treino
df_final = pd.concat([df_filtrado, imovel_dummies, condo_dummies], axis=1)

# ==========================================
# 4. Definição de Variáveis X e y
# ==========================================
features_numericas = ['condominio', 'iptu', 'metragem', 'quartos', 'banheiros', 'vagas']
features_categoricas = ['bairro']
features_binarias = list(imovel_dummies.columns) + list(condo_dummies.columns)

X = df_final[features_numericas + features_categoricas + features_binarias]
y = df_final['preco']

# Separação em Treino e Teste
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ==========================================
# 5. Pipeline de Pré-processamento e Modelo
# ==========================================
# Criamos transformadores apenas para numérica e categórica. As binárias passam direto.
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), features_numericas),
        ('cat', OneHotEncoder(handle_unknown='ignore'), features_categoricas)
    ],
    remainder='passthrough' # Mantém as colunas binárias intactas (0 e 1)
)

modelo = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
])

# Treinamento
print("Treinando o novo modelo aprimorado...")
modelo.fit(X_train, y_train)

# ==========================================
# 6. Avaliação dos Resultados obtidos
# ==========================================
print("Avaliando desempenho...")
y_pred = modelo.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n--- NOVOS RESULTADOS ---")
print(f"R² (Score de explicação): {r2:.4f}")
print(f"Erro Médio Absoluto (MAE): R$ {mae:,.2f}")
print(f"Raiz do Erro Quadrático Médio (RMSE): R$ {rmse:,.2f}")

print("\n--- NOVO EXEMPLO PRÁTICO ---")
df_exemplo = X_test.head(5).copy()
df_exemplo['Preco Real'] = y_test.head(5).values
df_exemplo['Preco Previsto'] = modelo.predict(X_test.head(5))
print(df_exemplo[['bairro', 'metragem', 'Preco Real', 'Preco Previsto']])