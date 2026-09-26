package com.studyhub.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import com.studyhub.android.data.Dashboard
import kotlinx.coroutines.launch

@Composable
fun DashboardScreen(
    model: AppModel,
    onOpenNote: (Int) -> Unit,
    onOpenGroup: (Int) -> Unit,
    onSignOut: () -> Unit,
) {
    var data by remember { mutableStateOf<Dashboard?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var loading by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    fun load() {
        scope.launch {
            loading = true
            error = null
            try {
                data = model.api.dashboard()
            } catch (cause: Throwable) {
                error = cause
            } finally {
                loading = false
            }
        }
    }

    LaunchedEffect(Unit) { load() }

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = "Dashboard", style = MaterialTheme.typography.headlineSmall)
                Text(
                    text = model.user?.username.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            OutlinedButton(onClick = onSignOut) { Text("Sign out") }
        }

        val current = data
        when {
            current == null && loading -> Loading("Loading your dashboard…")
            current == null && error != null -> Column(modifier = Modifier.padding(16.dp)) {
                ErrorNote(error)
                Button(onClick = ::load) { Text("Try again") }
            }
            current != null -> DashboardBody(
                data = current,
                error = error,
                onOpenNote = onOpenNote,
                onOpenGroup = onOpenGroup,
                onRetry = ::load,
            )
        }
    }
}

@Composable
private fun DashboardBody(
    data: Dashboard,
    error: Throwable?,
    onOpenNote: (Int) -> Unit,
    onOpenGroup: (Int) -> Unit,
    onRetry: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (error != null) {
            item {
                ErrorNote(error)
                Button(onClick = onRetry) { Text("Try again") }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatCard(label = "Notes", value = data.totalNotes.toString(), modifier = Modifier.weight(1f))
                StatCard(label = "Done", value = data.doneNotes.toString(), modifier = Modifier.weight(1f))
                StatCard(
                    label = "Unfiled",
                    value = data.withoutSubject.toString(),
                    modifier = Modifier.weight(1f),
                )
            }
        }

        if (data.bySubject.isNotEmpty()) {
            item {
                val max = data.bySubject.maxOf { it.count }
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text("Notes by subject", style = MaterialTheme.typography.titleMedium)
                        data.bySubject.forEach { subject ->
                            SubjectBar(name = subject.name, count = subject.count, color = subject.color, max = max)
                        }
                    }
                }
            }
        }

        if (data.byKind.any { it.count > 0 }) {
            item {
                val max = data.byKind.maxOf { it.count }
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text("By type", style = MaterialTheme.typography.titleMedium)
                        data.byKind.forEach { row ->
                            SubjectBar(name = row.label, count = row.count, color = null, max = max)
                        }
                    }
                }
            }
        }

        if (data.bySemester.any { it.count > 0 }) {
            item {
                val max = data.bySemester.maxOf { it.count }
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text("By semester", style = MaterialTheme.typography.titleMedium)
                        data.bySemester.forEach { row ->
                            SubjectBar(name = row.label, count = row.count, color = null, max = max)
                        }
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("Recently edited", style = MaterialTheme.typography.titleMedium)
                    if (data.recentNotes.isEmpty()) {
                        Text(
                            text = "No notes yet",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    data.recentNotes.forEach { note ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onOpenNote(note.id) }
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = if (note.isDone) "✓ " else "• ",
                                color = MaterialTheme.colorScheme.primary,
                            )
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = note.title,
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                                Text(
                                    text = "by ${note.author} · Sem ${note.semester} · ${note.branch} · " +
                                        shortDate(note.updatedAt),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }

        if (data.groups.isNotEmpty()) {
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("Your groups", style = MaterialTheme.typography.titleMedium)
                        data.groups.forEach { group ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onOpenGroup(group.id) }
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(group.name, style = MaterialTheme.typography.bodyLarge)
                                    val preview = group.lastMessage
                                    Text(
                                        text = preview?.let { "${it.sender}: ${it.body}" }
                                            ?: "No messages yet",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text(
                                    text = "${group.memberCount}",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(modifier = modifier) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = value, style = MaterialTheme.typography.headlineSmall)
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SubjectBar(name: String, count: Int, color: String?, max: Int) {
    val fraction = if (max <= 0) 0f else count.toFloat() / max
    val barColor = runCatching { Color(android.graphics.Color.parseColor(color ?: "#2f5fe0")) }
        .getOrDefault(MaterialTheme.colorScheme.primary)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row {
            Text(
                text = name,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = count.toString(),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Box(
            modifier = Modifier
                .fillMaxWidth(fraction.coerceIn(0.05f, 1f))
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(barColor),
        )
    }
}

internal fun shortDate(timestamp: String): String = timestamp.take(10)
