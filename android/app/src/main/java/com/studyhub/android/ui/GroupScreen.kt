package com.studyhub.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import com.studyhub.android.data.ChatSocket
import com.studyhub.android.data.Group
import com.studyhub.android.data.GroupMember
import com.studyhub.android.data.ChatMessage
import kotlinx.coroutines.launch

private const val HISTORY_PAGE = 50

@Composable
fun GroupScreen(
    model: AppModel,
    groupId: Int,
    onBack: () -> Unit,
    onSignedOut: () -> Unit,
) {
    var group by remember { mutableStateOf<Group?>(null) }
    var members by remember { mutableStateOf<List<GroupMember>>(emptyList()) }
    var messages by remember { mutableStateOf<List<ChatMessage>?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var socketError by remember { mutableStateOf<String?>(null) }
    var status by remember { mutableStateOf("connecting") }
    var draft by remember { mutableStateOf("") }
    var attempt by remember { mutableStateOf(0) }
    var showMembers by remember { mutableStateOf(false) }
    var confirmLeave by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var chatSocket by remember { mutableStateOf<ChatSocket?>(null) }
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current
    val listState = rememberLazyListState()

    fun append(incoming: ChatMessage) {
        val current = messages ?: return
        messages = if (current.any { it.id == incoming.id }) current else current + incoming
    }

    LaunchedEffect(groupId) {
        try {
            error = null
            val loadedGroup = model.api.group(groupId)
            val loadedMembers = model.api.members(groupId)
            val history = model.api.messages(groupId, limit = HISTORY_PAGE)
            group = loadedGroup
            members = loadedMembers
            messages = history
        } catch (cause: Throwable) {
            error = cause
        }
    }

    DisposableEffect(groupId, attempt, group?.id) {
        val chat = if (group == null) null else ChatSocket(
            api = model.api,
            token = model.session.token,
            groupId = groupId,
            listener = object : ChatSocket.Listener {
                override fun onConnected() {
                    scope.launch { status = "online" }
                }

                override fun onMessage(message: ChatMessage) {
                    scope.launch { append(message) }
                }

                override fun onError(detail: String) {
                    scope.launch { socketError = detail }
                }

                override fun onClosed(code: Int, reason: String) {
                    scope.launch {
                        status = "offline"
                        if (code == 4401) {
                            model.signOut()
                            onSignedOut()
                        } else if (code == 4404) {
                            error = Exception("You are not a member of this group any more")
                        }
                    }
                }
            },
        )
        if (chat != null) {
            status = "connecting"
            socketError = null
            chat.connect()
            chatSocket = chat
        }
        onDispose {
            chat?.close()
            chatSocket = null
        }
    }

    LaunchedEffect(messages?.size) {
        val size = messages?.size ?: 0
        if (size > 0) listState.animateScrollToItem(size - 1)
    }

    fun send() {
        val body = draft.trim()
        if (body.isEmpty()) return
        draft = ""
        socketError = null
        if (chatSocket?.send(body) == true) return
        scope.launch {
            try {
                append(model.api.sendMessage(groupId, body))
            } catch (cause: Throwable) {
                socketError = messageOf(cause)
            }
        }
    }

    fun loadOlder() {
        val oldest = messages?.firstOrNull() ?: return
        scope.launch {
            try {
                val older = model.api.messages(groupId, beforeId = oldest.id, limit = HISTORY_PAGE)
                messages = older + (messages ?: emptyList())
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    if (confirmLeave) {
        ConfirmDialog(
            title = "Leave group?",
            message = "You will need a new invite code to come back.",
            onConfirm = {
                confirmLeave = false
                scope.launch {
                    try {
                        model.api.leaveGroup(groupId)
                        onBack()
                    } catch (cause: Throwable) {
                        error = cause
                    }
                }
            },
            onDismiss = { confirmLeave = false },
        )
    }

    if (confirmDelete) {
        ConfirmDialog(
            title = "Delete group?",
            message = "The group and its messages are removed for everyone.",
            onConfirm = {
                confirmDelete = false
                scope.launch {
                    try {
                        model.api.deleteGroup(groupId)
                        onBack()
                    } catch (cause: Throwable) {
                        error = cause
                    }
                }
            },
            onDismiss = { confirmDelete = false },
        )
    }

    val currentGroup = group
    val currentMessages = messages
    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Text(
                text = currentGroup?.name ?: "Group",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.weight(1f),
            )
            StatusDot(status = status)
        }

        currentGroup?.let { loaded ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = loaded.inviteCode,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                TextButton(onClick = {
                    clipboard.setText(AnnotatedString(loaded.inviteCode))
                    socketError = "Invite code copied"
                }) { Text("Copy") }
                TextButton(onClick = { showMembers = !showMembers }) {
                    Text("Members (${members.size})")
                }
                if (loaded.myRole == "owner") {
                    TextButton(onClick = { confirmDelete = true }) { Text("Delete") }
                } else {
                    TextButton(onClick = { confirmLeave = true }) { Text("Leave") }
                }
            }
        }

        if (showMembers) {
            Card(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    members.forEach { member ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = member.username,
                                style = MaterialTheme.typography.bodyLarge,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                text = member.role,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        ErrorNote(error)
        socketError?.let { detail ->
            Text(
                text = detail,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(vertical = 4.dp),
            )
        }

        when {
            currentMessages == null -> Loading("Opening the group…")
            currentMessages.isEmpty() -> EmptyState(
                title = "No messages yet",
                message = "Say hello — everyone here will see it live.",
            )
            else -> LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).heightIn(max = 520.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 8.dp),
            ) {
                if (currentMessages.size >= HISTORY_PAGE) {
                    item {
                        TextButton(onClick = ::loadOlder) { Text("Load earlier messages") }
                    }
                }
                items(currentMessages, key = { it.id }) { message ->
                    ChatBubble(message = message, mine = message.senderId == model.user?.id)
                }
            }
        }

        if (status == "offline") {
            OutlinedButton(
                onClick = { attempt += 1 },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Reconnect") }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                placeholder = { Text("Write a message…") },
                modifier = Modifier.weight(1f),
                singleLine = true,
            )
            Button(onClick = ::send, enabled = draft.isNotBlank()) { Text("Send") }
        }
    }
}

@Composable
internal fun ChatBubble(message: ChatMessage, mine: Boolean) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (mine) Alignment.End else Alignment.Start,
    ) {
        Text(
            text = "${message.sender} · ${message.createdAt.take(16).replace('T', ' ')}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Card(modifier = Modifier.fillMaxWidth(0.8f)) {
            Text(
                text = message.body,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(10.dp),
            )
        }
    }
}

@Composable
internal fun StatusDot(status: String) {
    val label = when (status) {
        "online" -> "Live"
        "connecting" -> "Connecting…"
        else -> "Offline"
    }
    val color = when (status) {
        "online" -> MaterialTheme.colorScheme.primary
        "connecting" -> MaterialTheme.colorScheme.onSurfaceVariant
        else -> MaterialTheme.colorScheme.error
    }
    Text(
        text = "● $label",
        style = MaterialTheme.typography.bodySmall,
        color = color,
    )
}

@Composable
private fun ConfirmDialog(
    title: String,
    message: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Yes") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
