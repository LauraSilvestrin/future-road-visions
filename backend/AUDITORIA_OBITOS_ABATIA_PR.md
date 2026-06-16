# Auditoria da métrica `mortos` — Abatiá (PR)

Data da auditoria: 2026-06-16  
Escopo: município `ABATIA` / UF `PR`  
Fonte da métrica: coluna `mortos` em `municipio_ano.csv`.

## 1. Coluna que alimenta `mortos`

A variável exibida como óbitos/mortos é alimentada diretamente pela coluna `mortos` dos CSVs agregados:

- `municipio_ano.csv`: `ano; uf; municipio; acidentes; mortos; feridos; pessoas`
- `uf_ano.csv`: `ano; uf; acidentes; mortos; feridos; pessoas`
- `regiao_ano.csv`: `ano; regiao; acidentes; mortos; feridos`
- `causa_ano.csv`: `ano; causa_acidente; acidentes; mortos`
- `clima_ano.csv`: `ano; condicao_metereologica; acidentes; mortos`

Para esta auditoria municipal, a origem efetiva é `backend/data/municipio_ano.csv`, coluna `mortos`.

## 2. Carregamento e conversão de tipos

O carregador normaliza nomes de colunas e converte `mortos` com `pd.to_numeric`. A rotina foi reforçada para:

- remover espaços e separadores de milhar;
- converter vírgula decimal para ponto;
- falhar explicitamente se houver valor não numérico não vazio;
- evitar transformar strings inválidas em zero silenciosamente.

Resultado observado para Abatiá (PR): `mortos` carregado como `int64`, sem valores negativos e sem falha de conversão.

## 3. Distribuição real da coluna `mortos`

Recorte analisado: 8 registros anuais.

| Estatística | Valor |
|---|---:|
| Registros válidos | 8 |
| Zeros | 4 |
| Positivos | 4 |
| Negativos | 0 |
| Mínimo | 0 |
| P25 | 0 |
| Mediana | 0,5 |
| Média | 0,5 |
| P75 | 1 |
| Máximo | 1 |

Frequência dos valores:

| Valor | Frequência |
|---:|---:|
| 0 | 4 |
| 1 | 4 |

## 4. Série histórica real utilizada

| Ano | Mortos reais |
|---:|---:|
| 2018 | 1 |
| 2019 | 0 |
| 2020 | 1 |
| 2021 | 1 |
| 2022 | 1 |
| 2023 | 0 |
| 2024 | 0 |
| 2025 | 0 |

## 5. Dados de treino

Nenhum registro válido de Abatiá (PR) foi eliminado por filtro nesta auditoria. O treino usou os mesmos 8 pontos históricos:

| Ano | Mortos no treino |
|---:|---:|
| 2018 | 1 |
| 2019 | 0 |
| 2020 | 1 |
| 2021 | 1 |
| 2022 | 1 |
| 2023 | 0 |
| 2024 | 0 |
| 2025 | 0 |

## 6. Filtros avaliados

- Filtro de município: agora compara texto normalizado sem acentos, então `Abatiá` encontra corretamente `ABATIA`.
- Filtro de UF: `PR`.
- Filtro de anos parciais: aplicado apenas quando a base contém anos detectados como coleta parcial; no recorte de Abatiá, a série observada vai até 2025.
- Resultado: nenhum registro histórico válido de `mortos` foi descartado para Abatiá (PR).

## 7. Arredondamento e causa dos zeros na interface

O problema principal não estava no CSV. A série histórica tem valores baixos, e o modelo retornava valores brutos fracionários muito próximos de zero. Em seguida:

1. o pós-processamento antigo permitia `floor = 0` quando havia anos com zero no histórico;
2. a interface usava `Math.round(...)` em cards e tooltips;
3. valores esperados como `0,39` óbito/ano eram exibidos como `0`.

Correção aplicada:

- a métrica `mortos` agora preserva expectativa fracionária positiva quando há histórico com óbitos positivos;
- o damping de óbitos não usa apenas a média dos últimos três anos quando eles são todos zero;
- a UI exibe óbitos fracionários menores que 1 com duas casas decimais em vez de arredondar para zero;
- o console registra valor histórico, previsão bruta, pós-processamento e valor final exibido.

## 8. Previsão bruta ano a ano até 2050

Modelo escolhido na reprodução local: `XGBoost`.  
Valor bruto retornado pelo modelo para os anos futuros: aproximadamente `0,0004584499` óbito/ano.

| Ano | Previsão bruta |
|---:|---:|
| 2026 | 0,000458 |
| 2027 | 0,000458 |
| 2028 | 0,000458 |
| 2029 | 0,000458 |
| 2030 | 0,000458 |
| 2031 | 0,000458 |
| 2032 | 0,000458 |
| 2033 | 0,000458 |
| 2034 | 0,000458 |
| 2035 | 0,000458 |
| 2036 | 0,000458 |
| 2037 | 0,000458 |
| 2038 | 0,000458 |
| 2039 | 0,000458 |
| 2040 | 0,000458 |
| 2041 | 0,000458 |
| 2042 | 0,000458 |
| 2043 | 0,000458 |
| 2044 | 0,000458 |
| 2045 | 0,000458 |
| 2046 | 0,000458 |
| 2047 | 0,000458 |
| 2048 | 0,000458 |
| 2049 | 0,000458 |
| 2050 | 0,000458 |

## 9. Previsão após pós-processamento

O pós-processamento aplica limite inferior positivo para óbitos quando a série tem pelo menos um ano com óbito registrado. Isso evita que expectativa estatística positiva seja exibida como ausência absoluta de óbitos.

| Ano | Pós-processamento | Motivo se zerado |
|---:|---:|---|
| 2026 | 0,100000 | — |
| 2027 | 0,111331 | — |
| 2028 | 0,154632 | — |
| 2029 | 0,191437 | — |
| 2030 | 0,222721 | — |
| 2031 | 0,249313 | — |
| 2032 | 0,271916 | — |
| 2033 | 0,291129 | — |
| 2034 | 0,307459 | — |
| 2035 | 0,321340 | — |
| 2036 | 0,333139 | — |
| 2037 | 0,343169 | — |
| 2038 | 0,351693 | — |
| 2039 | 0,358939 | — |
| 2040 | 0,365098 | — |
| 2041 | 0,370334 | — |
| 2042 | 0,374784 | — |
| 2043 | 0,378566 | — |
| 2044 | 0,381781 | — |
| 2045 | 0,384514 | — |
| 2046 | 0,386837 | — |
| 2047 | 0,388811 | — |
| 2048 | 0,390490 | — |
| 2049 | 0,391916 | — |
| 2050 | 0,393129 | — |

Valor final esperado na interface em 2050: `0,39` óbito/ano, não `0`.

## 10. Conclusão

Para Abatiá (PR), o zero exibido em 2050 era uma combinação de escala estatística baixa e arredondamento prematuro. A coluna `mortos` está presente e carrega corretamente. A projeção de óbitos deve ser interpretada como valor esperado anual fracionário em séries raras, não como contagem inteira determinística.
