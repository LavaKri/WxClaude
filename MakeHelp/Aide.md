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

Pour utiliser Claude Code, il est obligatoire de s'authentifier :

- dans un terminal, lancez `claude auth login` et suivez les instructions.
- Vérification avec `claude auth status`.

### Claude dans WxClaude

Dans l'onglet "Claude" des préférences, il sera possible de définir l'utilisation du programme Claude Code.

Notamment, le type d'interface est la façon dont les questions de permission de Claude parviennent à WxClaude.
Il s'applique au message suivant et peut être changé à tout moment.

- **Protocole stdio** (par défaut) :
toutes les questions de permission, les questions structurées de Claude et l'approbation de ses plans.
- **Hook HTTP** :
les questions de permission sur les outils. WxClaude démarre pour cela un serveur HTTP local sur 127.0.0.1.

Avec le hook HTTP, une question sans réponse dans le délai d'attente est refusée par Claude Code. Réglez ce délai (1 à 10 minutes) sur la même page.

Dans le mode de permission *Ne pas demander*, rien n'est demandé, quel que soit le type.

## Fonctionnement

### Espaces de travail

Un espace de travail est simplement un dossier de travail. Claude y travaille et en lit les fichiers.

- Fichier > Ouvrir depuis les projets Claude liste les dossiers déjà utilisés avec Claude Code.
- Au démarrage, le dernier espace de travail est rouvert. Vous pouvez le désactiver dans les Préférences, page Général.
- Outils > Paramètres de l'espace de travail modifie les règles de permission du dossier `.claude`. Elles sont partagées avec Claude Code dans un terminal.

### Conversations

Une conversation appartient toujours à un espace de travail. Ouvrir un espace de travail charge sa conversation mémorisée, sinon la plus récente. Une conversation n'est jamais créée automatiquement.

- Conversation > Reprendre une conversation liste celles de l'espace de travail, la plus récente d'abord.
- Conversation > Actualiser la conversation relit le fichier de session. 
- Conversation > Nouvelle branche de conversation copie la conversation sous un autre nom. Le texte reste affiché. La copie est faite par Claude Code avec le premier message de la branche ; la conversation d'origine ne change pas.
- Conversation > Supprimer la conversation met à la Corbeille de Windows ce que Claude Code garde de la conversation, après confirmation. Vous pouvez la récupérer depuis la Corbeille.

Conversation > Modifier l'agent change l'agent de la conversation courante.
Changer de modèle fait perdre le cache de l'invite de la conversation. Changer l'effort ou le mode de permission ne le fait pas.

### Agents

Un agent est un ensemble de caractéristiques.
Pour WxClaude, il se limite à un modèle, un effort et un mode de permission.

Deux agents se définissent dans les Préférences, page Agent :

- celui des nouvelles conversations, par défaut.
Il est propre à une conversation et pourra être modifié indépendamment des autres.
- un agent alternatif.
L'agent alternatif a son propre bouton d'envoi et il sera le même pour tous les espaces de travail.
Il sera utile pour envoyer facilement des prompts avec un niveau d'effort faible, par exemple, sans avoir à modifier l'agent principal.

### Permissions

Quand Claude veut utiliser un outil que le mode de permission n'autorise pas, une boîte de dialogue pose la question. La barre d'état l'annonce.

- *Autoriser* autorise l'outil cette fois.
- *Toujours autoriser* écrit une règle dans `.claude/settings.local.json`, comme le fait Claude Code. Ce bouton apparaît quand Claude Code propose une règle.
- *Refuser* refuse. Vous pouvez saisir une explication envoyée à Claude.

Fermer la boîte avec Échap est un refus. Le premier champ décrit la demande et reçoit le focus initial.

Les paramètres de l'espace de travail permettent de donner à chaque outil une règle d'autorisation, de demande ou de refus. Le refus l'emporte sur la demande, et la demande sur l'autorisation.

## Interface utilisateur

### Zone de conversation

La zone de conversation affiche l'échange en lecture seule.
Votre message est un titre de niveau 1. La réponse de Claude est un titre de niveau 2.
Parcourez-la avec la navigation par titres de votre lecteur d'écran.

Elle ne prend jamais le focus quand une réponse arrive.
Elle le prend quand vous chargez, envoyez, actualisez ou cherchez.

Vous pouvez y chercher du texte. La recherche ne revient pas au début : à la fin, elle vous le dit.

Le menu contextuel dépend du message où se trouve le curseur. Il ne propose que ce qui s'applique :

- *Afficher les outils utilisés* : quand la réponse a utilisé des outils. Une liste donne le détail de chacun.
- *Afficher le tableau* : quand le curseur est dans un tableau. Ses lignes sont lues une par une. Vous pouvez copier le tableau.
- *Afficher les liens* : quand le message en contient. Vous pouvez ouvrir un lien web ou de messagerie, ou copier l'adresse.

### Prompt

Le prompt est le champ où vous écrivez votre message à Claude.
Il peut contenir plusieurs lignes. Son menu contextuel est celui de Windows.
Il est grisé tant qu'il n'y a pas de conversation active.

Deux boutons envoient le message : l'un avec l'agent de la conversation, l'autre avec l'agent alternatif.
Pendant que Claude répond, l'envoi est grisé. Le champ reste utilisable pour de la saisie.

Le bouton *Interrompre Claude* arrête la réponse et les programmes lancés par Claude.
Il n'est actif que pendant une réponse.

### Barre d'état

La barre d'état a trois zones. Elle ne prend pas le focus : utilisez la commande de votre lecteur d'écran pour la lire.

- La position : `Message 3 sur 8` indique le message où se trouve le curseur parmi les vôtres. Elle est vide s'il n'y en a pas.
- L'étape : `Étape 2 sur 5 : sujet` indique la tâche de la liste de Claude qu'il vient de commencer. Elle est vide s'il n'y en a pas et quand WxClaude attend votre message.
- Le message : la dernière annonce. Quand WxClaude attend votre message, il dit `Prêt`, suivi de la jauge des 5 heures si elle est connue : `Prêt, jauge à 50 %`. La semaine s'y ajoute à partir de 75 % : `Prêt, jauge à 50 %, semaine à 76 %`. Après un échec, il garde l'erreur.

### Annonces

WxClaude dit ce qui se passe à votre lecteur d'écran. Les annonces sont regroupées en catégories.

Dans l'onglet "Lecteur d'écran" des préférences, vous choisissez pour chaque catégorie ce qui est fait.
Selon la catégorie : rien, un message, la lecture de la ligne, une boîte de dialogue ou un son.
Le choix *Annonces* coupe ou rétablit l'envoi vers le lecteur d'écran.

Les erreurs de Claude ouvrent toujours une boîte de dialogue.

#### Alertes de jauge

L'abonnement a deux jauges : la fenêtre de 5 heures et la semaine.
Chaque alerte est dite la première fois que la jauge atteint ou dépasse son seuil.
Les seuils sont ceux de Claude Code : 90 % pour les 5 heures, 25, 50 et 75 % pour la semaine.

### Tâches, plans et utilisation

Trois fenêtres d'information s'ouvrent à la demande. Elles montrent ce que WxClaude sait au moment de l'ouverture.

- La liste de tâches donne les tâches que Claude s'est fixées pour la conversation : numéro, sujet et état (en attente, en cours, terminée). Une ligne dit aussi ce qui la bloque. Le détail de la tâche choisie est dessous.
- Les plans sont ceux que Claude a écrits dans le mode de permission *Planifier seulement*. Ils sont en lecture seule : il n'y a rien à approuver ici.
- L'utilisation montre les jauges de l'abonnement et leur remise à zéro. Elle donne aussi des informations sur les jetons utilisés.
