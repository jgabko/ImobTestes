import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

df = pd.read_csv('imoveis_limpos.csv')

features_numericas = df['condominio', 'iptu', 'metragem', 'quartos', 'banheiros', 'vagas']
features_categoricas = df['bairro']




#stephanafk e vitti




