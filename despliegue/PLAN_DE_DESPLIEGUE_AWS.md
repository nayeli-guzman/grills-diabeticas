# Diseño y plan de despliegue en AWS

## 1. Propósito y alcance

Este documento propone cómo llevar a producción el sistema de predicción de reingreso hospitalario a 30 días. Cubre la arquitectura de implementación, el flujo de datos, la inferencia, el monitoreo, la adaptación ante *drift*, la promoción de modelos, la operación, la seguridad y los costos.

Diagrama editable de esta propuesta: [arquitectura-despliegue-aws.drawio](arquitectura-despliegue-aws.drawio).

La propuesta parte de los resultados reales del proyecto, no solo de una arquitectura genérica:

- Random Forest tabular de CPU como modelo principal, con artefacto actual de aproximadamente 18 MB;
- latencia local p95 de 79,5 ms, todavía no equivalente a latencia extremo a extremo;
- aproximadamente 50 000 altas/año como supuesto del caso de negocio, no como volumen observado;
- etiqueta disponible 30 días después del alta, más el retraso de llegada de datos;
- estrategia adaptativa E3 con ventana deslizante de tres bloques como la mejor alternativa evaluada;
- monitoreo E4 con una sola activación observada, todavía insuficiente para automatizar promociones;
- 37,6 % de casos con incertidumbre alta y razón mínima de selección de 0,38 frente al objetivo de 0,80.

Por estas dos últimas brechas, el sistema puede desplegarse inicialmente **en sombra**, pero sus predicciones no deben usarse todavía como insumo para priorizar pacientes en producción hasta cerrar las condiciones de salida descritas en la sección 13.

## 2. Requisitos que condicionan el diseño

| Requisito | Consecuencia de diseño |
|---|---|
| La predicción se solicita durante el alta | Se necesita inferencia síncrona y privada, con respuesta rápida y degradación segura. |
| El modelo únicamente predice riesgo | No recomienda ni ejecuta intervenciones, no asigna recursos y no modifica prescripciones o altas. El profesional interpreta la predicción y decide fuera del modelo. |
| Los datos clínicos son sensibles | Cifrado, acceso mínimo, red privada, auditoría y separación entre identidad clínica y datos analíticos. |
| El resultado se conoce después de 30 días | Predicciones y resultados se concilian de manera asíncrona; nunca se considera negativo un caso aún inmaduro. |
| Existe *data drift* y *concept drift* | Se separan el servicio online y los procesos batch de monitoreo/reentrenamiento. |
| El cupo de intervención es 15 % por cohorte | La puntuación individual y la asignación del recurso son decisiones distintas; el cupo global no se puede aplicar correctamente dentro de una llamada aislada. |
| El volumen de producción no está confirmado | Se elige una base de bajo costo que pueda migrar sin cambiar el contrato de la API. |
| El dataset no contiene fechas reales | Los diez bloques históricos no se convierten directamente en meses; la cadencia debe recalibrarse con datos locales fechados. |

## 3. Decisiones de despliegue

### 3.1 Encapsulamiento: microservicios por responsabilidad operativa

Se conserva la decisión de usar microservicios, pero no se divide preprocesamiento, calibración y predicción en llamadas de red independientes. Esas piezas deben vivir en **un único servicio de inferencia** y en un único artefacto versionado para evitar latencia, fallos parciales y diferencias entre entrenamiento e inferencia.

Los límites recomendados son:

1. **Servicio de inferencia:** valida el contrato, genera exactamente las mismas variables que en entrenamiento, calcula probabilidad calibrada e incertidumbre y devuelve el resultado.
2. **Proceso clínico consumidor:** fuera del modelo, el hospital puede consultar los scores de una cohorte para gestionar su capacidad. La decisión de priorizar y cualquier intervención corresponden al personal clínico.
3. **Pipeline de datos y etiquetas:** valida eventos, reconstruye historia disponible a cada corte y madura la etiqueta a 30 días.
4. **Pipeline MLOps:** monitorea, reentrena, evalúa, registra y despliega candidatos.

Esta separación responde a distintos ciclos de carga y cambio: la inferencia está siempre disponible; el uso clínico de sus resultados ocurre en el EHR; el monitoreo y entrenamiento son batch.

### 3.2 Entorno físico: contenedores Docker sobre CPU

Cada componente ejecutable se empaqueta como imagen OCI/Docker y se publica en Amazon ECR. La imagen fija versiones de Python, `scikit-learn`, `xgboost` y demás dependencias, e incluye pruebas del contrato de entrada y del artefacto.

No se justifican GPU ni instancias de alto rendimiento: el modelo es tabular, el artefacto es pequeño y la medición local está muy por debajo del objetivo. La capacidad final se decide con una prueba de carga que incluya las diez réplicas de incertidumbre, red y escritura de auditoría.

### 3.3 Plataforma: FaaS para inferencia y MLaaS/PaaS para el ciclo de ML

La plataforma recomendada para el piloto es híbrida:

- **AWS Lambda con imagen de contenedor y concurrencia aprovisionada** para la inferencia síncrona. Encaja con un volumen medio bajo, elimina la administración de servidores y evita mantener un endpoint de ML dedicado encendido todo el mes. La concurrencia aprovisionada reduce el riesgo de arranque en frío durante las horas de altas.
- **Amazon SageMaker AI Processing, Training, Pipelines y Model Registry** para preparar datos, entrenar, evaluar y gobernar versiones. Los jobs son efímeros y se pagan durante su ejecución.
- **Amazon S3** como fuente versionada de datos analíticos, predicciones, etiquetas, reportes y artefactos.
- **Amazon EventBridge Scheduler** para cadencias y **CloudWatch/EventBridge/SNS** para métricas e incidentes.

No se recomienda inicialmente:

- **EC2/IaaS:** añade parches, disponibilidad y escalado manual sin una necesidad del modelo.
- **EKS/Kubernetes:** su complejidad operativa no se justifica con cuatro componentes y bajo tráfico.
- **SageMaker Real-Time Endpoint dedicado:** es una buena ruta de crecimiento, pero mantiene capacidad permanente. Se migrará a él si Lambda no cumple memoria, tiempo, concurrencia o latencia tras la prueba real.
- **SageMaker Serverless sin capacidad aprovisionada:** el arranque en frío es incompatible con una garantía clínica estricta de latencia.
- **On-premises:** aumenta operación y dificulta el ciclo MLOps. Solo se reconsidera si la política del hospital impide procesar los datos en una región AWS aprobada.

La decisión se revisa con estas reglas: migrar a SageMaker Real-Time o ECS/Fargate si la concurrencia sostenida hace más cara a Lambda, si el paquete excede sus límites prácticos o si se requiere control más fino del servidor. El contrato REST y la imagen se mantienen, por lo que la migración no afecta al EHR.

El monitoreo se implementa con jobs propios, en lugar de depender de métricas genéricas de una plataforma: así se conservan exactamente PSI, KS/χ² con Bonferroni, calibración, reglas E4, costos y equidad definidos y validados en el proyecto.

### 3.4 Portabilidad y escalabilidad

- Imágenes en ECR, configuración externa y artefactos inmutables; nada de rutas o secretos embebidos.
- Infraestructura como código con AWS CloudFormation o AWS CDK sobre CloudFormation.
- Separación de cuentas o, como mínimo, entornos `dev`, `staging` y `prod`, con claves y roles distintos.
- Escalado de Lambda por concurrencia; SageMaker crea cómputo batch solo cuando se ejecuta un job.
- No se introduce un Feature Store en el piloto. El EHR envía una instantánea completa de los datos disponibles al alta y el mismo código reconstruye variables offline. Se añadirá un almacén online solo si aparecen variables que el EHR no puede entregar con consistencia.

### 3.5 Nivel de autonomía: modelo predictivo, sin autonomía operativa

El modelo se limita a calcular la probabilidad de reingreso, su incertidumbre y los factores que sustentan la predicción. No recomienda una intervención, no genera órdenes, no asigna recursos y no actúa sobre el EHR. El profesional recibe esa información como un dato adicional y toma de forma independiente cualquier decisión clínica.

Debe registrarse qué predicción se mostró y quién la consultó para fines de trazabilidad, sin representar la decisión posterior como una acción del modelo. Ante datos inválidos, timeout o indisponibilidad, el resultado es **“no evaluado”**; nunca se sustituye por una predicción de bajo riesgo.

El reentrenamiento puede ser automático; la promoción a producción no. Requiere aprobación de una persona responsable de ML y otra responsable clínica.

### 3.6 Integración: API REST privada con adaptador EHR

El contrato externo será REST/JSON, expuesto por Amazon API Gateway privado. El hospital accede desde su red mediante VPN o Direct Connect y un endpoint privado. Si el EHR usa HL7/FHIR, un adaptador del lado de integración transforma el recurso clínico al contrato canónico; el modelo no debe acoplarse a una marca de EHR.

La petición usa un identificador seudónimo del episodio, versión de esquema, hora real de alta y los datos disponibles en ese instante. La identidad del paciente permanece en el EHR. La respuesta incluye:

- probabilidad calibrada de reingreso;
- intervalo de incertidumbre e indicador de incertidumbre alta;
- versión de modelo y criterios de interpretación;
- estado de calidad de datos;
- factores explicativos aprobados para el usuario clínico;
- `request_id` para trazabilidad.

## 4. Componentes AWS propuestos

| Capa | Servicios | Responsabilidad |
|---|---|---|
| Conectividad | VPC en al menos dos zonas, VPN/Direct Connect, VPC endpoints | Mantener el tránsito privado y reducir exposición a Internet. |
| API | API Gateway privado, Lambda de inferencia | Autenticar, validar, preprocesar y puntuar. |
| Imágenes | Amazon ECR | Versionar imágenes escaneadas de inferencia y jobs. |
| Datos | S3 con versionado y SSE-KMS | Zonas `raw`, `validated`, `features`, `predictions`, `labels`, `reports` y `artifacts`. |
| Auditoría online | DynamoDB | Índice ligero e idempotente de solicitud, predicción, versión y estado; sin identidad clínica directa. |
| Desacoplamiento | SQS con cola de mensajes fallidos | Persistir eventos de predicción y tareas de integración sin retrasar innecesariamente la respuesta. |
| ML | SageMaker Processing, Training, Pipelines y Model Registry | Preparar, entrenar, evaluar y registrar candidatos. |
| Programación | EventBridge Scheduler | Iniciar conciliación, monitoreo y pipelines. |
| Operación | CloudWatch, EventBridge, SNS, CloudTrail | Métricas, alarmas, avisos técnicos y auditoría de API. |
| Seguridad | IAM, KMS, Secrets Manager | Mínimo privilegio, cifrado y secretos rotables. |

Se evita AWS Transfer Family en la línea base: no tiene sentido pagar un servidor SFTP permanente si el hospital puede usar la API privada o depositar lotes mediante un mecanismo ya aprobado. Se añade únicamente cuando SFTP sea un requisito real de integración.

## 5. Flujos de operación

### 5.1 Inferencia durante el alta

1. El EHR arma una instantánea con solo información conocida hasta la hora de alta.
2. API Gateway autentica y envía la petición a Lambda.
3. Lambda valida versión, tipos, rangos, campos obligatorios y frescura. Una clave de idempotencia evita puntuar dos veces el mismo episodio por un reintento.
4. El contenedor aplica preprocesamiento, modelo, calibrador y réplicas de incertidumbre del mismo paquete.
5. Se persiste el evento seudónimo y su versión; la API devuelve el resultado al EHR.
6. El EHR muestra la predicción como información clínica adicional. A partir de ella y de los demás antecedentes, el profesional decide si corresponde alguna acción; esa decisión no forma parte del modelo.

Objetivos iniciales: disponibilidad mensual de 99,9 % para el piloto, latencia p95 de API menor de 1 s y latencia visible en el EHR menor de 2 s. El resultado local de 79,5 ms no demuestra estos objetivos; se verifican con prueba extremo a extremo.

### 5.2 Consumo de las predicciones por el proceso clínico

El límite analítico de 15 % es una propiedad de una cohorte, no de una persona. El sistema puede generar cada cuatro horas un reporte de scores nuevos y métricas de la cohorte, pero **no asigna automáticamente el recurso ni actualiza una orden clínica**. El equipo autorizado del hospital aplica su política de capacidad fuera del modelo y decide a qué pacientes atender.

La política humana debe definir sede, horizonte, capacidad disponible, manejo de empates y casos urgentes. No se propondrán umbrales distintos por raza o edad sin evaluación clínica, ética y legal. Durante el piloto se compararán cupos estratificados y postprocesamiento de igualdad de oportunidad como análisis, pero su eventual uso pertenece a la gobernanza clínica, no al modelo predictivo.

### 5.3 Maduración de etiquetas

1. El hospital envía altas, reingresos, correcciones y evidencia de cobertura de otras sedes.
2. Los lotes originales quedan inmutables en S3; una validación de esquema, conteos, duplicados y fechas decide si avanzan o pasan a cuarentena.
3. Un reingreso confirmado dentro de 30 días produce etiqueta positiva.
4. Una etiqueta negativa solo se publica después de 30 días más un margen de llegada tardía calibrado con el hospital.
5. Cobertura incompleta, identidad ambigua o corrección pendiente produce `pendiente/no_evaluable`, nunca un cero.
6. Cada etiqueta conserva la versión de reglas y la fecha en que se volvió conocible.

En producción, el embargo de 2 000 `encounter_id` se reemplaza por tiempo real. Las variables históricas solo usan hechos que ya eran conocibles en la fecha de cada predicción.

### 5.4 Monitoreo, entrenamiento y promoción

1. El monitoreo semanal sin etiqueta calcula calidad, volumen, categorías nuevas, PSI y KS/χ².
2. La evaluación mensual usa únicamente cohortes maduras para ROC-AUC, PR-AUC, Brier, calibración, costo, incertidumbre, selección y FNR por subgrupo.
3. Cada nueva cohorte madura permite crear un candidato E3 con las tres últimas cohortes válidas. “Tres” describe el número de ventanas, no tres meses por defecto; un backtest local fijará duración y muestra mínima.
4. Una señal E4 puede adelantar la investigación y la creación de un candidato extraordinario, pero no su promoción.
5. El pipeline registra el candidato como `PendingManualApproval`, junto con hashes de datos, código, imagen, métricas y reporte por subgrupo.
6. Tras aprobaciones ML y clínica, el candidato corre en sombra y luego en canario. Alarmas de errores y latencia provocan rollback a la versión anterior.

## 6. Paquete desplegable del modelo

El paquete promovido debe ser una unidad inmutable y contener:

- esquema y orden de variables;
- transformaciones y codificadores;
- modelo principal y calibrador;
- las diez réplicas usadas para incertidumbre, o un método sustituto validado;
- bins y distribuciones de referencia para monitoreo;
- versión de la política clínica y umbrales;
- versiones de librerías, código y datos;
- métricas de validación y hash del contenido.

El `modelo_calibrado.pkl` actual no contiene las diez réplicas: estas se usan para generar `scores_test.csv`, pero no se serializan. Por tanto, el artefacto actual **no puede reproducir en producción la incertidumbre descrita en el informe** y no es promovible sin corregir el empaquetado. Además, un archivo `pickle` solo debe cargarse desde un bucket controlado, con checksum y rol restringido, porque no es un formato seguro frente a contenido no confiable.

## 7. Compuertas de calidad y promoción

Un candidato avanza únicamente si cumple todos estos grupos:

1. **Datos:** esquema compatible, cobertura y retraso dentro del SLA, sin fugas en la batería de trece pruebas y sin cohortes inmaduras.
2. **Software:** pruebas unitarias, integración, contrato, vulnerabilidades críticas y equivalencia notebook-servicio superadas.
3. **Modelo:** no inferior al activo en PR-AUC, Brier/calibración y costo clínico con márgenes aprobados; métricas con intervalos, no solo estimaciones puntuales.
4. **Seguridad:** imagen firmada, procedencia verificable, mínimo privilegio y ausencia de PHI en logs.
5. **Equidad:** límites aprobados de FNR, selección y calibración por subgrupo, con tamaño mínimo reportado.
6. **Operación:** prueba de carga, canario, rollback y procedimiento de revisión humana comprobados.
7. **Gobernanza:** aprobación ML y clínica, motivo del cambio, vigencia y plan de reversión registrados.

Una alerta de *drift* no implica que el candidato sea mejor. Si falla una compuerta, se mantiene el modelo vigente o se suspende la ayuda automatizada; nunca se promueve para “resolver” el *drift* sin evidencia.

## 8. Monitoreo y respuesta operativa

Se observan cuatro planos:

- **Servicio:** disponibilidad, p50/p95/p99, 4xx/5xx, timeouts, concurrencia, throttling y cola fallida.
- **Datos:** volumen, completitud, valores fuera de rango, categorías nuevas, duplicados, frescura y cobertura de resultados.
- **Modelo:** distribución del score, PSI, KS/χ², ROC-AUC, PR-AUC, Brier, pendiente/intercepto de calibración y costo esperado.
- **Impacto:** porcentaje seleccionado por el proceso clínico, FNR y calibración por subgrupo, consulta de predicciones, contacto dentro de siete días y reingreso observado.

Se proponen tres niveles:

| Nivel | Ejemplos | Acción |
|---|---|---|
| P1 | Servicio inaccesible, predicciones corruptas, exposición de datos | Derivar a revisión humana, congelar tráfico o revertir; guardia técnica y responsable clínico. |
| P2 | PSI > 0,25 en al menos dos variables clave, degradación con etiquetas maduras, lote ausente | Investigar en cuatro horas; bloquear entrenamiento/promoción afectado. |
| P3 | Tendencia de costo, capacidad o calidad sin impacto inmediato | Registrar y revisar en la reunión operativa. |

Las alarmas técnicas nunca contienen identidad ni variables clínicas. Los resultados asociados a un paciente solo se muestran dentro del EHR; no se envían por SNS, correo ni CloudWatch.

Objetivos iniciales de recuperación: RTO de 30 minutos para el servicio de soporte y RPO cercano a cero para predicciones confirmadas, mediante idempotencia y cola persistente. Durante una caída, la operación clínica continúa manualmente.

## 9. Seguridad, privacidad y cumplimiento

- Elegir la región después de validar residencia de datos y normativa aplicable. Si se procesa PHI bajo HIPAA, la organización debe tener un BAA con AWS y limitarse a servicios elegibles; que un servicio sea elegible no vuelve conforme al sistema por sí solo.
- TLS en tránsito, SSE-KMS en S3/DynamoDB y claves separadas por entorno.
- Roles IAM por tarea, sin credenciales largas; secretos en Secrets Manager.
- S3 Block Public Access, políticas por prefijo, VPC endpoints y egreso restringido.
- Logs estructurados con `request_id`, versión y estado, sin nombre, historia clínica ni payload completo.
- CloudTrail, retención definida, inventario de acceso y revisiones periódicas.
- Separar el mapa identidad–seudónimo, que debe permanecer bajo control hospitalario.
- Documentar versión, propósito, limitaciones, población, variables, explicación y supervisión humana para transparencia clínica.
- Definir retención y eliminación con el hospital; no conservar datos “por si acaso”.

Referencias oficiales: [servicios AWS elegibles para HIPAA](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/), [seguridad de Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/security.html) y [API privadas de API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-private-apis.html).

## 10. Escalabilidad y costo

El principal supuesto de negocio —50 000 altas/año— equivale a unas 137 predicciones diarias en promedio, pero no describe picos por hora ni número de sedes. Se presupuestará con escenarios de pico, no solo con el promedio.

Los principales inductores son:

- concurrencia aprovisionada y duración/memoria de Lambda;
- horas de Processing/Training y número de réplicas;
- almacenamiento y retención en S3;
- logs y métricas de CloudWatch;
- VPN o Direct Connect;
- ambientes adicionales y soporte;
- SFTP, NAT Gateway o endpoints privados solo si realmente son necesarios.

La línea base serverless evita los tres costos fijos más altos de la propuesta anterior: dos instancias de endpoint siempre activas, un servidor Transfer Family permanente y una colección sobredimensionada de endpoints de interfaz. Antes del piloto se calcularán tres escenarios en AWS Pricing Calculator —volumen esperado, doble volumen y pico de diez veces— y se configurarán AWS Budgets al 80 % y 100 %.

La optimización no puede sacrificar seguridad clínica: se mantiene capacidad aprovisionada en horario operativo y una prueba sintética periódica. Fuera del horario, la concurrencia puede programarse según el SLA real del hospital.

## 11. Plan por fases

### Fase 0 — Cierre de bloqueantes

- Resolver y validar la brecha de selección equitativa.
- Definir cómo operar el 37,6 % de incertidumbre alta o recalibrar su criterio.
- Empaquetar réplicas y probar equivalencia de inferencia.
- Aprobar definición clínica de reingreso, población elegible y política de intervención.

**Salida:** decisión `go/no-go` para modo sombra; todavía sin influir en atención.

### Fase 1 — Productización reproducible

- Extraer preprocesamiento/modelo desde notebooks a librerías probadas.
- Crear imagen Docker y contrato REST versionado.
- Añadir pruebas unitarias, de fuga, esquema y regresión de predicciones.
- Crear infraestructura como código para `dev` y `staging`.

**Salida:** misma predicción dentro y fuera del notebook, dentro de tolerancia numérica acordada.

### Fase 2 — Datos y MLOps offline

- Crear buckets, cifrado, roles, validación, cuarentena y conciliación.
- Implementar Pipelines, Processing/Training y Model Registry.
- Ejecutar backtest con fechas reales y recalibrar ventana, margen de etiqueta y mínimos muestrales.
- Configurar monitoreo y reportes mensuales.

**Salida:** candidato reproducible registrado, sin endpoint clínico.

### Fase 3 — Inferencia en sombra

- Integrar API privada y Lambda con un EHR de prueba.
- Puntuar sin mostrar recomendaciones ni asignar recursos.
- Medir latencia, picos, errores, calidad, cobertura, sesgo y concordancia con el pipeline offline.
- Probar caída, reintento, duplicados, recuperación y rollback.

**Salida:** informe de sombra y aprobación clínica/seguridad.

### Fase 4 — Piloto asistido

- Mostrar resultado a un grupo controlado de profesionales.
- Mantener confirmación obligatoria y protocolo alternativo manual.
- Medir comprensión y utilidad de la predicción, contacto a siete días, carga del equipo y posible fatiga informativa.
- Comparar impacto con diseño prospectivo aprobado; no atribuir causalidad solo a métricas históricas.

**Salida:** decisión de ampliar, corregir o retirar.

### Fase 5 — Escala y mejora continua

- Ampliar sedes gradualmente.
- Revisar capacidad, costo y necesidad de migrar a SageMaker Real-Time/ECS.
- Revalidar modelo y política ante cambios de población, EHR o práctica clínica.
- Ejecutar simulacros de rollback y revisión de acceso al menos trimestralmente.

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación principal |
|---|---|
| Selección inequitativa | Bloquear uso clínico hasta validar una política; revisar por subgrupo en cada promoción. |
| Demasiados casos inciertos | Dimensionar revisión humana y ajustar criterio solo con validación temporal/prospectiva. |
| Fuga temporal | Hora de corte explícita, etiqueta madura y repetición de las trece pruebas. |
| Entrenamiento e inferencia distintos | Una librería y un paquete de transformaciones compartidos; pruebas de paridad. |
| *Drift* silencioso | Calidad diaria, *drift* semanal y desempeño mensual con etiquetas maduras. |
| Reentrenamiento que empeora | Registro pendiente, comparación contra activo, sombra/canario y aprobación humana. |
| Cuota del 15 % mal interpretada como decisión del modelo | Reportar scores por cohorte; la asignación la realiza el proceso clínico externo bajo una política versionada. |
| Historia incompleta entre hospitales | Estado `no_evaluable`; medir cobertura y no interpretar ausencia como negativo. |
| Caída del servicio | “No evaluado”, flujo manual, cola idempotente y rollback probado. |
| Costo o complejidad excesiva | Serverless inicial, recursos condicionales y revisión por métricas reales. |
| Dependencia de `pickle` | Procedencia controlada, hash/firma, versiones fijadas y migración futura a formato menos acoplado cuando sea viable. |

## 13. Condiciones mínimas antes de producción clínica

El sistema solo deja el modo sombra cuando:

1. el uso clínico externo de las predicciones cumple el criterio de equidad aprobado —incluida la razón de selección— o existe una excepción clínica formalmente justificada;
2. el flujo de revisión puede absorber la incertidumbre alta observada;
3. el paquete reproduce score e incertidumbre y supera las pruebas de fuga;
4. las métricas se revalidan con fechas reales y población local;
5. el hospital confirma cobertura de reingresos, definición de etiqueta y retrasos;
6. la prueba extremo a extremo cumple latencia, disponibilidad y carga;
7. seguridad, privacidad, plan de incidentes, rollback y continuidad manual están aprobados;
8. un piloto prospectivo demuestra que las recomendaciones se usan de manera segura.

El Brier de 0,0963 frente al objetivo 0,095, el impacto proyectado de 3,8 % y la pérdida del escenario extremo de eficacia no se ocultan: deben figurar en la ficha del modelo y en la decisión clínica. No son por sí solos una razón para automatizar ni para descartar el piloto, pero sí impiden afirmar que todos los objetivos del proyecto ya se cumplen.

## 14. Decisiones pendientes que requieren al hospital

- región AWS y marco normativo aplicable;
- EHR, protocolo de integración y autenticación;
- volumen por hora, sedes y horario de disponibilidad;
- alcance de reingresos observables entre sedes;
- definición exacta de cohorte, exclusiones y transferencia;
- capacidad real de intervención y periodicidad de la cola;
- responsables clínicos/ML, SLA de incidentes y retención;
- costos locales, para sustituir los supuestos del caso de negocio.

Estas decisiones no cambian la estructura principal, pero sí la configuración, el costo y el criterio final de salida.

## 15. Referencias técnicas de AWS

- [Imágenes de contenedor para AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Concurrencia aprovisionada de Lambda](https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html)
- [Amazon SageMaker Pipelines](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines.html)
- [Amazon SageMaker Model Registry](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
- [Guardrails de despliegue de SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html)
- [Amazon EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html)
- [Seguridad de infraestructura en Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security.html)
