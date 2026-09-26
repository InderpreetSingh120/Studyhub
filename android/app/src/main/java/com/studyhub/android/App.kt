package com.studyhub.android

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.studyhub.android.data.Api
import com.studyhub.android.data.Session
import com.studyhub.android.data.TokenResponse
import com.studyhub.android.ui.ChatScreen
import com.studyhub.android.ui.DashboardScreen
import com.studyhub.android.ui.GroupScreen
import com.studyhub.android.ui.GroupsScreen
import com.studyhub.android.ui.LoginScreen
import com.studyhub.android.ui.NoteDetailScreen
import com.studyhub.android.ui.NoteEditorScreen
import com.studyhub.android.ui.NotesScreen
import com.studyhub.android.ui.RegisterScreen
import com.studyhub.android.ui.StudyHubTheme

/** Session-wide state: who is signed in, plus the API client bound to that session. */
@Stable
class AppModel(context: Context) {
    val session = Session(context)
    val api = Api(session)

    var user by mutableStateOf(session.user)
        private set

    val isSignedIn: Boolean get() = session.isSignedIn

    fun signIn(response: TokenResponse) {
        session.save(response.accessToken, response.user)
        user = response.user
    }

    fun signOut() {
        session.clear()
        user = null
    }
}

private data class Tab(val route: String, val label: String, val icon: ImageVector)

/** The core icon set has no speech bubble, so draw one. */
private val ChatBubble: ImageVector
    get() = ImageVector.Builder(
        name = "ChatBubble",
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
    ).apply {
        path(fill = SolidColor(Color(0xFF000000))) {
            moveTo(20f, 2f)
            lineTo(4f, 2f)
            curveTo(2.9f, 2f, 2f, 2.9f, 2f, 4f)
            verticalLineTo(22f)
            lineTo(6f, 18f)
            horizontalLineTo(20f)
            curveTo(21.1f, 18f, 22f, 17.1f, 22f, 16f)
            verticalLineTo(4f)
            curveTo(22f, 2.9f, 21.1f, 2f, 20f, 2f)
            close()
        }
    }.build()

private val tabs = listOf(
    Tab("dashboard", "Home", Icons.Filled.Home),
    Tab("notes", "Gallery", Icons.Filled.List),
    Tab("chat", "Chat", ChatBubble),
    Tab("groups", "Groups", Icons.Filled.Person),
)

@Composable
fun AppNavigation(model: AppModel) {
    val navController = rememberNavController()
    val start = if (model.isSignedIn) "dashboard" else "login"
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    val showTabs = tabs.any { it.route == currentRoute }

    fun goToLogin() {
        navController.navigate("login") {
            popUpTo(0) { inclusive = true }
        }
    }

    StudyHubTheme {
        Scaffold(
            bottomBar = {
                if (showTabs) {
                    NavigationBar {
                        tabs.forEach { tab ->
                            NavigationBarItem(
                                selected = currentRoute == tab.route,
                                onClick = {
                                    navController.navigate(tab.route) {
                                        popUpTo("dashboard") { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                },
                                icon = { Icon(tab.icon, contentDescription = tab.label) },
                                label = { Text(tab.label) },
                            )
                        }
                    }
                }
            },
        ) { padding ->
            NavHost(
                navController = navController,
                startDestination = start,
                modifier = Modifier.padding(padding),
            ) {
                routes(navController, model, ::goToLogin)
            }
        }
    }
}

private fun NavGraphBuilder.routes(
    navController: NavHostController,
    model: AppModel,
    goToLogin: () -> Unit,
) {
    fun openNote(id: Int) = navController.navigate("note/$id")
    fun openGroup(id: Int) = navController.navigate("group/$id")

    composable("login") {
        LoginScreen(
            model = model,
            onSignedIn = {
                navController.navigate("dashboard") {
                    popUpTo("login") { inclusive = true }
                }
            },
            onGoRegister = { navController.navigate("register") },
        )
    }
    composable("register") {
        RegisterScreen(
            model = model,
            onSignedIn = {
                navController.navigate("dashboard") {
                    popUpTo("login") { inclusive = true }
                }
            },
            onGoLogin = { navController.popBackStack() },
        )
    }
    composable("dashboard") {
        DashboardScreen(
            model = model,
            onOpenNote = ::openNote,
            onOpenGroup = ::openGroup,
            onSignOut = {
                model.signOut()
                goToLogin()
            },
        )
    }
    composable("notes") {
        NotesScreen(
            model = model,
            onOpenNote = ::openNote,
            onNewNote = { navController.navigate("note/new") },
        )
    }
    composable("note/new") {
        NoteEditorScreen(
            model = model,
            noteId = -1,
            onDone = { navController.popBackStack() },
        )
    }
    composable("note/{id}") { entry ->
        val id = entry.arguments?.getString("id")?.toIntOrNull() ?: -1
        NoteDetailScreen(
            model = model,
            noteId = id,
            onBack = { navController.popBackStack() },
            onEdit = { navController.navigate("note/$id/edit") },
            onDeleted = {
                navController.popBackStack()
            },
        )
    }
    composable("note/{id}/edit") { entry ->
        NoteEditorScreen(
            model = model,
            noteId = entry.arguments?.getString("id")?.toIntOrNull() ?: -1,
            onDone = { navController.popBackStack() },
        )
    }
    composable("chat") {
        ChatScreen(
            model = model,
            onSignedOut = goToLogin,
        )
    }
    composable("groups") {
        GroupsScreen(
            model = model,
            onOpenGroup = ::openGroup,
        )
    }
    composable("group/{id}") { entry ->
        GroupScreen(
            model = model,
            groupId = entry.arguments?.getString("id")?.toIntOrNull() ?: -1,
            onBack = { navController.popBackStack() },
            onSignedOut = goToLogin,
        )
    }
}
