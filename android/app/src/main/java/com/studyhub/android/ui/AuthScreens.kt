package com.studyhub.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.studyhub.android.AppModel
import kotlinx.coroutines.launch

/** Same collapsing rules the API applies, so mistakes surface before submit. */
internal fun normalizePhone(raw: String): String {
    val digits = raw.filter { it.isDigit() }
    return when {
        digits.length == 12 && digits.startsWith("91") -> digits.substring(2)
        digits.length == 13 && digits.startsWith("910") -> digits.substring(3)
        digits.length == 11 && digits.startsWith("0") -> digits.substring(1)
        else -> digits
    }
}

private val USERNAME = Regex("^[A-Za-z]+(?: [A-Za-z]+)*$")

@Composable
fun LoginScreen(
    model: AppModel,
    onSignedIn: () -> Unit,
    onGoRegister: () -> Unit,
) {
    var identifier by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    val scope = rememberCoroutineScope()

    fun submit() {
        scope.launch {
            busy = true
            error = null
            try {
                model.signIn(model.api.login(identifier.trim(), password))
                onSignedIn()
            } catch (cause: Throwable) {
                error = cause
            } finally {
                busy = false
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text = "StudyHub", style = MaterialTheme.typography.headlineMedium)
        Text(
            text = "Shared notes, summaries and study chats",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(modifier = Modifier.height(24.dp))
        StudyHubTextField(
            value = identifier,
            onValueChange = { identifier = it },
            label = "Phone number or username",
        )
        Spacer(modifier = Modifier.height(12.dp))
        StudyHubTextField(
            value = password,
            onValueChange = { password = it },
            label = "Password",
            password = true,
            keyboardType = KeyboardType.Password,
        )
        Spacer(modifier = Modifier.height(8.dp))
        ErrorNote(error)
        Spacer(modifier = Modifier.height(8.dp))
        PrimaryButton(
            text = "Sign in",
            onClick = ::submit,
            enabled = identifier.isNotBlank() && password.isNotBlank(),
            busy = busy,
        )
        TextButton(onClick = onGoRegister) { Text("Create an account") }
    }
}

@Composable
fun RegisterScreen(
    model: AppModel,
    onSignedIn: () -> Unit,
    onGoLogin: () -> Unit,
) {
    var username by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmation by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    val scope = rememberCoroutineScope()

    val trimmedName = username.trim().replace(Regex("\\s+"), " ")
    val nameOk = USERNAME.matches(trimmedName) && trimmedName.length >= 3
    val digits = normalizePhone(phone)
    val phoneOk = digits.length == 10
    val mismatch = confirmation.isNotEmpty() && confirmation != password

    fun submit() {
        scope.launch {
            busy = true
            error = null
            try {
                model.signIn(model.api.register(trimmedName, digits, password))
                onSignedIn()
            } catch (cause: Throwable) {
                error = cause
            } finally {
                busy = false
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(text = "Create account", style = MaterialTheme.typography.headlineMedium)
        Spacer(modifier = Modifier.height(24.dp))
        StudyHubTextField(
            value = username,
            onValueChange = { username = it },
            label = "Username (letters and spaces)",
        )
        if (username.isNotEmpty() && !nameOk) {
            Text(
                text = "Use letters only — no numbers or symbols",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        Spacer(modifier = Modifier.height(12.dp))
        StudyHubTextField(
            value = phone,
            onValueChange = { phone = it },
            label = "Phone number",
            keyboardType = KeyboardType.Phone,
        )
        if (phone.isNotEmpty() && !phoneOk) {
            Text(
                text = "10 digits; +91 and a leading 0 are fine",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        Spacer(modifier = Modifier.height(12.dp))
        StudyHubTextField(
            value = password,
            onValueChange = { password = it },
            label = "Password (8+ characters)",
            password = true,
            keyboardType = KeyboardType.Password,
        )
        Spacer(modifier = Modifier.height(12.dp))
        StudyHubTextField(
            value = confirmation,
            onValueChange = { confirmation = it },
            label = "Repeat password",
            password = true,
            keyboardType = KeyboardType.Password,
        )
        if (mismatch) {
            Text(
                text = "Passwords do not match",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Your display name is visible to everyone. Accounts with " +
                "unrecognized names may be renamed or removed by an administrator.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(modifier = Modifier.height(8.dp))
        ErrorNote(error)
        Spacer(modifier = Modifier.height(8.dp))
        PrimaryButton(
            text = "Create account",
            onClick = ::submit,
            enabled = nameOk && phoneOk && !mismatch && password.length >= 8,
            busy = busy,
        )
        TextButton(onClick = onGoLogin) { Text("I already have an account") }
    }
}
