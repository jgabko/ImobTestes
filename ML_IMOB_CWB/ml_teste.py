import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 1. Carregar os dados
# Certifique-se de que o arquivo CSV está na mesma pasta que o script
print("Carregando os dados...")
df = pd.read_csv('/home/JGMK/Documents/ImobTestes/ML_IMOB_CWB/imoveis_limpos.csv')

# 2. Definição de Features (X) e Target (y)
# Por enquanto, estamos ignorando as colunas de "caracteristicas" pois elas 
# estão em formato de lista de texto e exigem um tratamento mais avançado.
features_numericas = ['condominio', 'iptu', 'metragem', 'quartos', 'banheiros', 'vagas']
features_categoricas = ['bairro'] 
# Cidade, estado e CEP foram ignorados nesta versão base, pois parecem ser todos de Curitiba.

X = df[features_numericas + features_categoricas]
y = df['preco']

# 3. Separação em Treino e Teste (80% para treinar, 20% para testar)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Criação dos Transformadores
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), features_numericas),
        ('cat', OneHotEncoder(handle_unknown='ignore'), features_categoricas)
    ])

# 5. Montagem do Pipeline
# O pipeline garante que o dado de teste passe pelas exatas mesmas transformações do treino
modelo = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
])

# 6. Treinamento do Modelo
print("Treinando o modelo de Machine Learning (Random Forest)...")
modelo.fit(X_train, y_train)

# 7. Previsões e Avaliação
print("Avaliando o desempenho nos dados de teste...")
y_pred = modelo.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("\n--- Resultados ---")
print(f"R² (Score de explicação): {r2:.4f}")
print(f"Erro Médio Absoluto (MAE): R$ {mae:,.2f}")
print(f"Raiz do Erro Quadrático Médio (RMSE): R$ {rmse:,.2f}")

# Exemplo rápido: Prever o preço dos 5 primeiros imóveis do teste
print("\n--- Exemplo Prático ---")
df_exemplo = X_test.head(5).copy()
df_exemplo['Preco Real'] = y_test.head(5).values
df_exemplo['Preco Previsto'] = modelo.predict(X_test.head(5))
print(df_exemplo[['bairro', 'metragem', 'Preco Real', 'Preco Previsto']])