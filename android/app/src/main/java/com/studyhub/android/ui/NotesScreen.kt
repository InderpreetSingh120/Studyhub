package com.studyhub.android.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
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
import com.studyhub.android.data.KIND_LABELS
import com.studyhub.android.data.NOTE_KINDS
import com.studyhub.android.data.Note
import com.studyhub.android.data.Subject
import kotlinx.coroutines.launch

@Composable
fun NotesScreen(
    model: AppModel,
    onOpenNote: (Int) -> Unit,
    onNewNote: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var subjects by remember { mutableStateOf<List<Subject>>(emptyList()) }
    var notes by remember { mutableStateOf<List<Note>?>(null) }
    var selectedSubject by remember { mutableStateOf<Int?>(null) }
    var kindFilter by remember { mutableStateOf<String?>(null) }
    var mineOnly by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var showNewSubject by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            try {
                error = null
                notes = model.api.notes(
                    query = query,
                    subjectId = selectedSubject,
                    kind = kindFilter,
                    mine = if (mineOnly) true else null,
                )
            } catch (cause: Throwable) {
                error = cause
            }
        }
    }

    LaunchedEffect(Unit) {
        try {
            subjects = model.api.subjects()
        } catch (cause: Throwable) {
            error = cause
        }
    }

    LaunchedEffect(query, selectedSubject, kindFilter, mineOnly) { refresh() }

    if (showNewSubject) {
        NewSubjectDialog(
            model = model,
            onDismiss = { showNewSubject = false },
            onCreated = { subject ->
                showNewSubject = false
                subjects = subjects + subject
                selectedSubject = subject.id
            },
        )
    }

    Column(modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "Gallery", style = MaterialTheme.typography.headlineSmall)
                Text(
                    text = "Everyone's notes",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            OutlinedButton(onClick = onNewNote) { Text("Upload") }
        }

        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            label = { Text("Search title, body or author") },
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            singleLine = true,
        )

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(
                selected = selectedSubject == null,
                onClick = { selectedSubject = null },
                label = { Text("All subjects") },
            )
            subjects.forEach { subject ->
                FilterChip(
                    selected = selectedSubject == subject.id,
                    onClick = { selectedSubject = subject.id },
                    label = { Text(subject.name) },
                )
            }
            FilterChip(selected = false, onClick = { showNewSubject = true }, label = { Text("+ subject") })
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(bottom = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(
                selected = kindFilter == null,
                onClick = { kindFilter = null },
                label = { Text("Any type") },
            )
            NOTE_KINDS.forEach { kind ->
                FilterChip(
                    selected = kindFilter == kind,
                    onClick = { kindFilter = if (kindFilter == kind) null else kind },
                    label = { Text(KIND_LABELS.getValue(kind)) },
                )
            }
            FilterChip(
                selected = mineOnly,
                onClick = { mineOnly = !mineOnly },
                label = { Text("Only mine") },
            )
        }

        ErrorNote(error)

        val current = notes
        when {
            current == null -> Loading()
            current.isEmpty() -> EmptyState(
                title = "No notes here",
                message = "Be the first to share notes, or change the filters.",
            )
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 16.dp),
            ) {
                items(current, key = { it.id }) { note ->
                    NoteRow(note = note, subjects = subjects, onClick = { onOpenNote(note.id) })
                }
            }
        }
    }
}

@Composable
private fun NoteRow(note: Note, subjects: List<Subject>, onClick: () -> Unit) {
    val subject = subjects.firstOrNull { it.id == note.subjectId }
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = if (note.isDone) "✓ " else "• ",
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = note.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
            }
            Text(
                text = "by ${note.author} · Semester ${note.semester} · ${note.branch}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = note.kindLabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (subject != null) {
                    Text(
                        text = subject.name,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                if (note.attachmentCount > 0) {
                    Text(
                        text = "${note.attachmentCount} file",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = shortDate(note.updatedAt),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun NewSubjectDialog(
    model: AppModel,
    onDismiss: () -> Unit,
    onCreated: (Subject) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    val scope = rememberCoroutineScope()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New subject") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
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
                            onCreated(model.api.createSubject(name.trim(), null))
                        } catch (cause: Throwable) {
                            error = cause
                        } finally {
                            busy = false
                        }
                    }
                },
            ) { Text("Create") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
