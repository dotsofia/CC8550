# Plano de Testes - Sistema Anime Track

## 1. Objetivo
Garantir a qualidade e o correto funcionamento do sistema "Anime Track",
verificando todas as camadas (repositório, serviço e interface web) por meio de testes automatizados.

## 2. Escopo
Os testes cobrem:
- Funcionalidades CRUD das 5 entidades principais (Usuário, Anime, Estúdio, Tag, WatchEntry)
- Regras de negócio (validações, status, pontuação, duplicidade)
- Importação e exportação de dados
- Interface Web básica (rotas Flask)
- Persistência em repositório em memória e SQLite

## 3. Tipos de Teste
| Tipo                         | Ferramenta | Objetivo | Quantidade |
|------------------------------|-------------|-----------|-------------|
| Unitário                     | pytest      | Testar funções isoladas | 40+ |
| Integração                   | pytest      | Testar fluxo entre módulos/repos | 10 |
| Funcional (Caixa-Preta)      | pytest-flask | Testar rotas e saídas esperadas | 8 | 
| Específicos (API + Exceções) | requests, pytest | Validar status HTTP e erros | 9 | 
| Estruturais (Cobertura)      | pytest-cov  | Verificar cobertura de código | 19 |  
| Mutação                      | mutmut      | Avaliar eficácia dos testes | NÃO TESTADO | 

## 4. Ferramentas e Ambiente
- **Linguagem:** Python 3.13
- **Frameworks:** Flask, pytest, mutmut
- **Banco de dados:** SQLite (modo real) e InMemoryRepo (mock)
- **Ambiente de teste:** Windows 10 / Virtualenv
- **Comandos principais:**
  ```bash
  pytest -v
  pytest --cov=app --cov-report=html
```
## 5. Critérios de Aceitação

- Todos os testes devem passar sem falhas.  
- Cobertura de código **≥ 80%**.  
- Todas as regras de negócio devem estar validadas.
---

## 6. Riscos

- Falhas por dependências quebradas.  
- Erros em caminhos pouco utilizados (upload/erro de import).  

---

## 7. Critérios de Sucesso

- Todos os requisitos mínimos e testes exigidos no enunciado são atendidos.  
- O relatório final evidencia **alta cobertura** e **taxa de mutantes mortos**.

