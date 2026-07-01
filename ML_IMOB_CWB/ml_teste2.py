import pandas as pd
import numpy as np
import ast
import re
import joblib
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, MultiLabelBinarizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ==========================================
# 1. Carregamento e Limpeza
# ==========================================
print("Carregando os dados...")
df = pd.read_csv('/home/JGMK/Documents/ImobTestes/ML_IMOB_CWB/imoveis_limpos.csv')

print("Removendo outliers extremos...")
q1_preco, q3_preco = df['preco'].quantile(0.25), df['preco'].quantile(0.75)
limite_sup_preco = q3_preco + 1.5 * (q3_preco - q1_preco)
limite_inf_preco = max(0, q1_preco - 1.5 * (q3_preco - q1_preco))

q1_meta, q3_meta = df['metragem'].quantile(0.25), df['metragem'].quantile(0.75)
limite_sup_meta = q3_meta + 1.5 * (q3_meta - q1_meta)
limite_inf_meta = max(10, q1_meta - 1.5 * (q3_meta - q1_meta))

df_filtrado = df[
    (df['preco'] >= limite_inf_preco) & (df['preco'] <= limite_sup_preco) &
    (df['metragem'] >= limite_inf_meta) & (df['metragem'] <= limite_sup_meta)
].copy()

# ==========================================
# 2. Engenharia de Features Textuais
# ==========================================
print("Processando características textuais...")
def converter_para_lista(texto):
    if pd.isna(texto) or not isinstance(texto, str): return []
    try: return ast.literal_eval(texto)
    except: return []

df_filtrado['caracteristicas_imovel'] = df_filtrado['caracteristicas_imovel'].apply(converter_para_lista)
df_filtrado['caracteristicas_condominio'] = df_filtrado['caracteristicas_condominio'].apply(converter_para_lista)

mlb_imovel = MultiLabelBinarizer()
imovel_dummies = pd.DataFrame(
    mlb_imovel.fit_transform(df_filtrado['caracteristicas_imovel']),
    columns=[f"imovel_{c.lower().replace(' ', '_')}" for c in mlb_imovel.classes_],
    index=df_filtrado.index
)

mlb_condo = MultiLabelBinarizer()
condo_dummies = pd.DataFrame(
    mlb_condo.fit_transform(df_filtrado['caracteristicas_condominio']),
    columns=[f"condo_{c.lower().replace(' ', '_')}" for c in mlb_condo.classes_],
    index=df_filtrado.index
)

df_final = pd.concat([df_filtrado, imovel_dummies, condo_dummies], axis=1)
df_final.columns = [re.sub(r'[\[\]<>{}]', '', str(col)) for col in df_final.columns]

# ==========================================
# 3. Preparação das Variáveis
# ==========================================
features_numericas = ['condominio', 'iptu', 'metragem', 'quartos', 'banheiros', 'vagas']
features_categoricas = ['bairro']
features_binarias = [re.sub(r'[\[\]<>{}]', '', str(col)) for col in list(imovel_dummies.columns) + list(condo_dummies.columns)]

X = df_final[features_numericas + features_categoricas + features_binarias]
y = df_final['preco']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), features_numericas),
        ('cat', OneHotEncoder(handle_unknown='ignore'), features_categoricas)
    ],
    remainder='passthrough'
)

# ==========================================
# 4. O Campeonato (Hyperparameter Tuning)
# ==========================================
pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(random_state=42))
])

# Aqui definimos as opções que o algoritmo vai testar
parametros_busca = {
    'regressor__n_estimators': [100, 200, 300, 400],           # Quantidade de árvores
    'regressor__max_depth': [None, 10, 20, 30],                # Profundidade das árvores
    'regressor__min_samples_split': [2, 5, 10],                # Mínimo de amostras para dividir um nó
    'regressor__min_samples_leaf': [1, 2, 4],                  # Mínimo de amostras na folha final
    'regressor__max_features': ['sqrt', 'log2', 1.0]           # Quantidade de features avaliadas por vez
}

print("\nIniciando a busca pela melhor configuração (Isso pode demorar alguns minutos)...")
# O n_iter=20 significa que ele vai sortear 20 combinações diferentes do dicionário acima
busca_aleatoria = RandomizedSearchCV(
    estimator=pipeline,
    param_distributions=parametros_busca,
    n_iter=20,
    cv=5,                                  # Validação cruzada em 5 fatias (5 folds)
    scoring='neg_mean_absolute_error',     # O objetivo do campeonato é o menor MAE
    random_state=42,
    n_jobs=-1,                             # Usa todos os núcleos do seu processador
    verbose=2                              # Mostra o progresso na tela
)

busca_aleatoria.fit(X_train, y_train)

# ==========================================
# 5. Avaliação do Campeão
# ==========================================
melhor_modelo = busca_aleatoria.best_estimator_

print("\n=== TREINAMENTO CONCLUÍDO ===")
print("Melhores parâmetros encontrados:")
for param, valor in busca_aleatoria.best_params_.items():
    print(f" -> {param}: {valor}")

print("\nAvaliando desempenho nos dados de teste...")
y_pred = melhor_modelo.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n=== RESULTADOS FINAIS DO MODELO TUNADO ===")
print(f"R² (Score de explicação): {r2:.4f}")
print(f"Erro Médio Absoluto (MAE): R$ {mae:,.2f}")
print(f"Raiz do Erro Quadrático Médio (RMSE): R$ {rmse:,.2f}")

# Salvando o modelo definitivo
if mae < 80000:
    print(f"\n✅ META ALCANÇADA! Reduzimos o erro para menos de 80 mil.")
else:
    print(f"\n⚠️ Chegamos no limite matemático dos dados disponíveis. O MAE estabilizou em R$ {mae:,.2f}.")

joblib.dump(melhor_modelo, 'rf_modelo_definitivo.pkl')
print("Modelo salvo com sucesso no arquivo 'rf_modelo_definitivo.pkl'!")