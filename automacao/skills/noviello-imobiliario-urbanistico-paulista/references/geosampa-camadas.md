# GeoSampa — Camadas Indispensáveis e Uso Operacional

> **Uso:** consulte este guia para conduzir uma due diligence urbanística rigorosa via GeoSampa. **Toda DD paulistana começa pelo GeoSampa** — sem o SQL e o cruzamento de camadas, qualquer parecer é abstrato.
>
> **URL:** geosampa.prefeitura.sp.gov.br
> **Catálogo de metadados:** metadados.geosampa.prefeitura.sp.gov.br/geonetwork/srv/por/catalog.search

---

## 1. Como buscar um lote

1. Abrir geosampa.prefeitura.sp.gov.br.
2. Inserir endereço, ou número de contribuinte, ou coordenadas (latitude/longitude), ou SQL.
3. Sistema retorna automaticamente: SQL (Setor/Quadra/Lote), zoneamento, macroárea, tombamento, ZEIS, APRM.
4. Ativar camadas adicionais conforme necessidade (ver itens 2-9).
5. Exportar mapa ou relatório em PDF.

---

## 2. Camadas regulatórias

### 2.1 Zoneamento (LPUOS vigente)
- **Para que serve:** identificar a sigla da zona (ZEU, ZER, ZEIS, etc.) → derivar parâmetros (CA, TO, gabarito).
- **Saída esperada:** sigla da zona + número do quadro da LPUOS aplicável.
- **Atenção:** verificar se a camada está atualizada com Lei 18.081/2024 e Lei 18.177/2024.

### 2.2 Macrozonas e Macroáreas (PDE)
- **Para que serve:** localizar o lote na macroestrutura do PDE (Lei 16.050/2014 + Lei 17.975/2023).
- **Saída esperada:** macrozona (Estruturação ou Proteção) + macroárea (MEM, MUC, MQU, MRVU, MRVRA, MCUUS, MPEN, MRAM).

### 2.3 Eixos de Estruturação
- **Para que serve:** verificar se o lote está em ZEU, ZEUa, ZEUP (previsto), ZEM, ZEMP.
- **Saída esperada:** status do eixo (ativo/previsto) → confirma se CA 4,0 já está disponível.

### 2.4 Mapa I da LPUOS (Lei 18.177/2024)
- **Para que serve:** mapa oficial vigente do zoneamento.
- **Saída esperada:** mapa atualizado para ser anexado em parecer.

### 2.5 Plano Diretor — mapas oficiais
- **Para que serve:** macrozoneamento, eixos, centralidades.
- **Saída esperada:** plano vigente com revisão Lei 17.975/2023.

---

## 3. Camadas de habitação social

### 3.1 ZEIS (todos os tipos)
- **Para que serve:** identificar incidência de ZEIS 1, 2, 3, 4 ou 5.
- **Saída esperada:** tipo de ZEIS + percentuais HIS aplicáveis.
- **Atenção:** Lei 17.975/2023 expandiu ZEIS em 23% — verificar se a camada reflete a expansão.

---

## 4. Camadas de operações e projetos urbanos

### 4.1 Operações Urbanas Consorciadas (OUC) + perímetros
- **Para que serve:** lote dentro de Faria Lima, Água Espraiada, Água Branca, Centro?
- **Saída esperada:** OUC aplicável + regime de CEPAC necessário.

### 4.2 PIU/AIU em estudo e aprovados
- **Para que serve:** lote afetado por Projeto/Área de Intervenção Urbana?
- **Saída esperada:** decreto/lei do PIU + parâmetros específicos.

---

## 5. Camadas ambientais e de risco

### 5.1 APRMs (Billings, Guarapiranga, Cantareira, Alto Tietê)
- **Para que serve:** restrições de proteção a mananciais.
- **Saída esperada:** lei estadual aplicável + PDPA (Plano de Desenvolvimento e Proteção Ambiental).
- **Leis específicas:** Billings 13.579/2009, Guarapiranga 12.233/2006.

### 5.2 APP intra-urbanas
- **Para que serve:** Áreas de Preservação Permanente urbanas (córregos, brejos, cabeceiras).
- **Base legal:** Lei 12.651/2012 (Código Florestal).
- **Saída esperada:** APP delimitada + restrições de ocupação.

### 5.3 Zonas de risco geotécnico
- **Para que serve:** áreas de escorregamento, inundação.
- **Saída esperada:** restrição de ocupação + necessidade de laudo geotécnico.

### 5.4 Áreas contaminadas (CETESB)
- **Para que serve:** cadastro de áreas com passivo ambiental.
- **Saída esperada:** estado de contaminação + tratamento exigido pela CETESB.

---

## 6. Camadas de patrimônio e proteção cultural

### 6.1 Bens tombados / ZEPEC
- **Para que serve:** identificar tombamentos CONPRESP (municipal) e CONDEPHAAT (estadual).
- **Saída esperada:** bem tombado + restrições de intervenção.

---

## 7. Camadas de restrição aeroportuária

### 7.1 Cones aeroportuários (CONAER)
- **Para que serve:** limites de altura próximos a Congonhas, Campo de Marte, Guarulhos.
- **Saída esperada:** gabarito máximo permitido (independente do gabarito da zona).

---

## 8. Camadas cadastrais e fiscais

### 8.1 Cadastro Imobiliário Fiscal (SQL)
- **Para que serve:** identificação espacial precisa do lote → base para IPTU, ITBI, OODC.
- **Saída esperada:** SQL + número do contribuinte.

### 8.2 Logradouros, lotes, quadras
- **Para que serve:** geolocalização precisa.
- **Saída esperada:** endereço completo + SQL.

### 8.3 Setor fiscal e Quadra fiscal
- **Para que serve:** consulta a IPTU e ITBI.

---

## 9. Como exportar e usar em parecer

1. **Exportar mapa:** clicar em "Imprimir" ou "Exportar" no menu superior do GeoSampa.
2. **Salvar como PDF:** usar visualizador padrão.
3. **Anexar ao parecer:** mapa + tabela de zoneamento + tabela de instrumentos aplicáveis.
4. **Citar a versão:** "Consulta GeoSampa em DD/MM/AAAA — Mapa I da LPUOS atualizado pela Lei 18.177/2024".

---

## 10. Limitações conhecidas

- **Defasagens pontuais:** lotes recém-alienados ou recém-desmembrados podem demorar para aparecer.
- **Integração com cartório ainda parcial:** sempre confirmar matrícula via SAEC (registradores.onr.org.br) ou RI Digital (ridigital.org.br).
- **Camadas em revisão:** quando há legislação recente (ex.: Lei 17.975/2023), pode haver atraso na atualização visual.

---

## 11. Sistemas complementares

### 11.1 SLC-e (Sistema Eletrônico de Licenciamento de Construções)
- URL: portaldelicenciamento.prefeitura.sp.gov.br
- Tipos: alvará comum, EZ (Empreendimento Zero Impacto), EIV/EZA, regularização.
- Integrado ao GeoSampa.

### 11.2 Approve Digital
- Para obras complexas (multipavimentos, OUC, BIM/CAD).
- Análise automática preliminar.

### 11.3 SISACOE
- Banco de dados histórico de alvarás.
- Controle de obras em execução.
- URL: www3.prefeitura.sp.gov.br/sd2110

### 11.4 SAEC / RI Digital
- Cartório eletrônico (matrícula, certidões).
- URL: registradores.onr.org.br | ridigital.org.br

---

## 12. Checklist de DD via GeoSampa (uso operacional)

Para qualquer caso paulistano, antes de emitir parecer:

- [ ] **SQL** identificado.
- [ ] **Zona** confirmada (LPUOS vigente).
- [ ] **Macroárea** identificada (PDE).
- [ ] **Eixo de estruturação?** ZEU/ZEM/ZEUP/ZEMP/ZEUa/ZEMPa.
- [ ] **ZEIS?** Tipo 1/2/3/4/5 + isenção por área < 1.000 m² (ou < 500 m² em ZEIS 3).
- [ ] **Dentro de OUC?** Faria Lima/Água Espraiada/Água Branca/Centro.
- [ ] **Em PIU/AIU?** verificar decreto regulamentador.
- [ ] **Em APRM?** Billings/Guarapiranga/Cantareira/Alto Tietê.
- [ ] **APP urbana?** córrego, brejo, cabeceira.
- [ ] **Zona de risco geotécnico?**
- [ ] **Área contaminada (CETESB)?**
- [ ] **Tombamento (CONPRESP/CONDEPHAAT) ou ZEPEC?**
- [ ] **Cone aeroportuário (CONAER)?** especialmente em zonas próximas a Congonhas, Campo de Marte, Guarulhos.
- [ ] **Mapa I e tabela de zoneamento exportados** para anexar ao parecer.
