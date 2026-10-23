# Aide de WxClaude

WxClaude est une interface de bureau pour la ligne de commande Claude Code, utilisée en mode non interactif (`claude -p`).
 Elle est conçue pour un usage avec lecteur d'écran et au clavier seul.
Elle utilise les contrôles natifs de Windows. 
Ce n'est pas un terminal.

## Installation et configuration

### Claude Code (claude -p)

WxClaude a besoin du programme Claude Code. 
Installez-le en suivant la [documentation de Claude Code](https://code.claude.com/docs/en/overview).

Vérifiez l'installation dans un terminal avec `claude --version`.

Pour utiliser Claude Code il est obligatoire de s'autentifier :
- dans un terminal, lancez `claude auth login` et suivez les instructions.
- Vérification avec `claude auth status`.

### Claude dans WxClaude
Dans l'onglet "Claude" des préférences il sera possible de définire l'utilisation du programme Claude Code

Notament, le type d'interface est la façon dont les questions de permission de Claude parviennent à WxClaude. 
Il s'applique au message suivant et peut être changé à tout moment.

- **Protocole stdio** (par défaut) : 
toutes les questions de permission, les questions structurées de Claude et l'approbation de ses plans.
- **Hook HTTP** : 
les questions de permission sur les outils. WxClaude démarre pour cela un serveur HTTP local sur 127.0.0.1.

Avec le hook HTTP, une question sans réponse dans le délai d'attente est refusée par Claude Code. Réglez ce délai (1 à 10 minutes) sur la même page.

Dans le mode de permission *Ne pas demander*, rien n'est demandé, quel que soit le type.

## Utilisation

### Espaces de travail

Un espace de travail est un dossier de travail. Claude y travaille et en lit les fichiers.

- Fichier > Ouvrir un espace de travail choisit un dossier.
- Fichier > Ouvrir depuis les projets Claude liste les dossiers déjà utilisés avec Claude Code.
- Fichier > Récents liste les derniers espaces de travail.
- Au démarrage, le dernier espace de travail est rouvert. Vous pouvez le désactiver dans les Préférences, page Général.
- Outils > Ouvrir le dossier de l'espace de travail l'affiche dans l'explorateur de fichiers.
- Outils > Paramètres de l'espace de travail modifie les règles de permission du dossier `.claude`. Elles sont partagées avec Claude Code dans un terminal.

Sans espace de travail, la plupart des éléments sont grisés. Ouvrir un autre espace de travail ferme la conversation courante.

### Conversations

Une conversation appartient toujours à un espace de travail. Ouvrir un espace de travail charge sa conversation mémorisée, sinon la plus récente. Une conversation n'est jamais créée automatiquement.

- Conversation > Nouvelle conversation en démarre une. Vous choisissez son nom.
- Conversation > Reprendre une conversation liste celles de l'espace de travail, la plus récente d'abord.
- Conversation > Renommer change le nom. Le nom n'est connu que de WxClaude.
- Conversation > Actualiser la conversation relit le fichier de session.
- Fichier > Exporter la conversation enregistre le texte dans un fichier.
- Conversation > Recherches cherche du texte dans la conversation.

La fenêtre principale contient la conversation, le champ de saisie, les boutons d'envoi, un bouton pour interrompre Claude et une barre d'état.

- Dans le champ de saisie, Entrée ajoute un saut de ligne. Les raccourcis d'envoi sont indiqués sur les boutons et modifiables dans les Préférences, page Raccourcis.
- Pendant que Claude répond, Envoyer est grisé. Le champ de saisie reste utilisable.
- Interrompre Claude arrête la réponse et les programmes lancés par Claude.
- La vue de la conversation ne prend jamais le focus à l'arrivée d'une réponse. Elle le prend quand vous chargez, envoyez, actualisez ou cherchez.
- La barre d'état indique votre position parmi vos messages, puis la dernière annonce.

### Agents

Un agent est un modèle, un effort et un mode de permission. Les trois sont toujours définis.

Deux agents se définissent dans les Préférences, page Agent : celui des nouvelles conversations et un agent alternatif. L'agent alternatif a son propre bouton d'envoi. Ses champs peuvent rester sur *comme la conversation*.

Conversation > Modifier l'agent change l'agent de la conversation courante.

Changer de modèle fait perdre le cache de l'invite de la conversation. Changer l'effort ou le mode de permission ne le fait pas.

### Permissions

Quand Claude veut utiliser un outil que le mode de permission n'autorise pas, une boîte de dialogue pose la question. La barre d'état l'annonce.

- *Autoriser* autorise l'outil cette fois.
- *Toujours autoriser* écrit une règle dans `.claude/settings.local.json`, comme le fait Claude Code. Ce bouton apparaît quand Claude Code propose une règle.
- *Refuser* refuse. Vous pouvez saisir une explication envoyée à Claude.

Fermer la boîte avec Échap est un refus. Le premier champ décrit la demande et reçoit le focus initial.

Les paramètres de l'espace de travail permettent de donner à chaque outil une règle d'autorisation, de demande ou de refus. Le refus l'emporte sur la demande, et la demande sur l'autorisation.

### Détails d'un message

Ouvrez le menu contextuel de la conversation sur un message pour voir les outils utilisés par Claude, ses tableaux et ses liens, ou pour copier le message ou tout l'échange (votre message et toutes les réponses de Claude). Seules les adresses web et de messagerie sont transmises au système.

Les Préférences, page Espace de travail, permettent de masquer les messages système écrits par Claude Code.

### Tâches, plans et utilisation

- Outils > Liste de tâches affiche les tâches écrites par Claude pour la conversation.
- Outils > Plan affiche les plans écrits par Claude dans le mode de permission *Planifier seulement*. Vous les lisez ici.
- Outils > Utilisation de Claude affiche les limites d'utilisation et les jetons dépensés. Elle se remplit avec les réponses reçues : elle est vide avant le premier message.

### Erreurs

Les erreurs de Claude vont dans la barre d'état et dans une boîte de dialogue, jamais dans le texte de la conversation. Si Claude ne peut pas être démarré, votre message est conservé.

Les annonces vont dans la barre d'état et, par UI Automation, à votre lecteur d'écran. Dans les Préférences, page Lecteur d'écran, choisissez pour chaque catégorie d'annonces ce qui est fait : rien, un message ou un son. Les erreurs de Claude ouvrent toujours une boîte de dialogue.
