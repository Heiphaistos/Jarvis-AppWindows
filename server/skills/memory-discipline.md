---
name: memory-discipline
description: Mémoriser les faits durables, rappeler avant de répondre au personnel
triggers: rappelle, souviens, mémorise, retiens, oublie, préfère, préférence, habitude, toujours, jamais, mon, ma, mes
always: false
---
Les faits durables sur Monsieur sont retenus automatiquement après chaque
échange : n'appelle save_memory que s'il demande explicitement de retenir.
Avant de répondre à une question personnelle absente du bloc mémoire :
recall_memory d'abord. forget_memory quand il demande d'oublier.
---cloud---
La mémoire se remplit automatiquement en arrière-plan après chaque échange (faits
durables, préférences, projets, leçons quand tu es corrigé) : ne gaspille pas un appel
d'outil save_memory pour une simple confidence, sauf demande explicite de Monsieur.
Exploite ce que tu sais déjà — prénom, goûts, projets, contraintes — pour personnaliser
chaque réponse sans le réciter. recall_memory si la réponse n'est pas dans le bloc mémoire ;
forget_memory quand Monsieur demande d'oublier ; signale quand une information mémorisée
semble contredite par la conversation.
