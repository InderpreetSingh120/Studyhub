package com.studyhub.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import com.studyhub.android.data.Group
import kotlinx.coroutines.launch

@Composable
fun GroupsScreen(
    model: AppModel,
    onOpenGroup: (Int) -> Unit,
) {
    var groups by remember { mutableStateOf<List<Group>?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var showDialog by remember { mutableStateOf<Dialog?>(null) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            try {
                error = null
                groups = model.api.groups()
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    LaunchedEffect(Unit) { refresh() }

    when (showDialog) {
        Dialog.Create -> NewGroupDialog(
            model = model,
            onDismiss = { showDialog = null },
            onCreated = { group ->
                showDialog = null
                onOpenGroup(group.id)
            },
        )
        Dialog.Join -> JoinGroupDialog(
            model = model,
            onDismiss = { showDialog = null },
            onJoined = { group ->
                showDialog = null
                onOpenGroup(group.id)
            },
        )
        null -> Unit
    }

    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = "Groups", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { showDialog = Dialog.Join }) { Text("Join") }
            TextButton(onClick = { showDialog = Dialog.Create }) { Text("New") }
        }

        ErrorNote(error)

        val current = groups
        when {
            current == null -> Loading()
            current.isEmpty() -> EmptyState(
                title = "No groups yet",
                message = "Create one, or join a friend's group with an invite code.",
            )
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(current, key = { it.id }) { group ->
                    Card(onClick = { onOpenGroup(group.id) }, modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(group.name, style = MaterialTheme.typography.titleMedium)
                            if (group.description.isNotBlank()) {
                                Text(
                                    text = group.description,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text(
                                    text = "${group.memberCount} member${if (group.memberCount == 1) "" else "s"}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Text(
                                    text = group.inviteCode,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

private enum class Dialog { Create, Join }

@Composable
private fun NewGroupDialog(
    model: AppModel,
    onDismiss: () -> Unit,
    onCreated: (com.studyhub.android.data.Group) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    val scope = rememberCoroutineScope()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New group") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("Description (optional)") },
                )
                ErrorNote(error)
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && !busy,
                onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            onCreated(model.api.createGroup(name.trim(), description.trim()))
                        } catch (cause: Throwable) {
                            error = cause
                        } finally {
                            busy = false
                        }
                    }
                },
            ) { Text("Create") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun JoinGroupDialog(
    model: AppModel,
    onDismiss: () -> Unit,
    onJoined: (com.studyhub.android.data.Group) -> Unit,
) {
    var code by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    val scope = rememberCoroutineScope()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Join a group") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it.uppercase() },
                    label = { Text("Invite code") },
                    singleLine = true,
                )
                ErrorNote(error)
            }
        },
        confirmButton = {
            TextButton(
                enabled = code.isNotBlank() && !busy,
                onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            onJoined(model.api.joinGroup(code))
                        } catch (cause: Throwable) {
                            error = cause
                        } finally {
                            busy = false
                        }
                    }
                },
            ) { Text("Join") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
