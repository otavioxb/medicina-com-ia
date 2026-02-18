CREATE OR REPLACE VIEW view_analytics_transcricao AS
SELECT 
    dc.id,
    dc.sessao_id,
    dc.patient_id,
    dc.necessidade,
    s.uid,
    dc.duracao_transcricao,
    dc.data
FROM duracao_consulta dc
INNER JOIN sessions s ON dc.sessao_id = s.sessao_id;

-- DROP VIEW IF EXISTS view_consultas_pendentes;
CREATE OR REPLACE VIEW view_consultas_pendentes AS
SELECT
    ct.sessao_id,
    ct.patient_id,
    ct.status,
    ct.updated_at,
    ct.necessidade,
    ct.transcricao_completa,
    s.uid
FROM
    complete_transcriptions ct
JOIN
    sessions s ON ct.sessao_id = s.sessao_id;