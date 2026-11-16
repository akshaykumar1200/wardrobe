package com.wardrobe.ootd

import android.os.Bundle
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items as lazyItems
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.painter.ColorPainter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.ImageLoader
import coil.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import java.io.File

// Same palette as the web app, so the two read as one product.
private val Sand = Color(0xFFF7F6F2)
private val Sage = Color(0xFF3B5B4C)
private val Ink = Color(0xFF1C1D1F)
private val Muted = Color(0xFF6B6F6D)
private val Danger = Color(0xFFB3261E)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = Store(this)
        val api = Api(store)
        // Coil shares the authenticating client, or every item image 404s.
        val imageLoader = ImageLoader.Builder(this).okHttpClient(api.client).build()
        setContent {
            val uploadViewModel: UploadViewModel = viewModel(factory = UploadViewModelFactory(api))
            val closetViewModel: ClosetViewModel = viewModel(factory = ClosetViewModelFactory(api))
            val outfitViewModel: OutfitViewModel = viewModel(factory = OutfitViewModelFactory(api))
            val wearViewModel: WearViewModel = viewModel(factory = WearViewModelFactory(api))
            val suggestViewModel: SuggestViewModel = viewModel(factory = SuggestViewModelFactory(api))
            val settingsViewModel: SettingsViewModel = viewModel(factory = SettingsViewModelFactory(api, store))
            App(store, api, imageLoader, uploadViewModel, closetViewModel, outfitViewModel, wearViewModel, suggestViewModel, settingsViewModel)
        }
    }
}

@Composable
private fun App(store: Store, api: Api, imageLoader: ImageLoader, uploadViewModel: UploadViewModel, closetViewModel: ClosetViewModel, outfitViewModel: OutfitViewModel, wearViewModel: WearViewModel, suggestViewModel: SuggestViewModel, settingsViewModel: SettingsViewModel) {
    var signedIn by remember { mutableStateOf(store.token != null) }
    var showRegistration by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(false) }
    var showOutfits by remember { mutableStateOf(false) }
    var showWears by remember { mutableStateOf(false) }
    var showSuggest by remember { mutableStateOf(false) }

    BackHandler(enabled = showSettings) { showSettings = false }
    BackHandler(enabled = showOutfits && !showWears && !showSuggest) { showOutfits = false }
    BackHandler(enabled = showSuggest) { showSuggest = false }
    BackHandler(enabled = showWears) { showWears = false }

    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Sage,
            onPrimary = Sand,
            primaryContainer = Sage,
            onPrimaryContainer = Sand,
            secondary = Sage,
            onSecondary = Sand,
            secondaryContainer = Sage,
            onSecondaryContainer = Sand,
            tertiary = Sage,
            onTertiary = Sand,
            tertiaryContainer = Sage,
            onTertiaryContainer = Sand,
            background = Sand,
            onBackground = Ink,
            surface = Sand,
            onSurface = Ink,
            surfaceDim = Sand,
            surfaceBright = Sand,
            surfaceContainerLowest = Sand,
            surfaceContainerLow = Sand,
            surfaceContainer = Sand,
            surfaceContainerHigh = Sand,
            surfaceContainerHighest = Sand,
            surfaceTint = Sage,
            surfaceVariant = Sand,
            onSurfaceVariant = Muted,
            error = Danger,
            onError = Sand,
            errorContainer = Danger,
            onErrorContainer = Sand,
            outline = Muted,
            outlineVariant = Muted,
            inverseSurface = Ink,
            inverseOnSurface = Sand,
            inversePrimary = Sage,
        ),
    ) {
        Surface(modifier = Modifier.fillMaxSize()) {
            if (signedIn) {
                if (showWears) {
                    WearHistoryScreen(api, imageLoader, wearViewModel, onBack = { showWears = false }, onSignedOut = {
                        showWears = false
                        signedIn = false
                    })
                } else if (showSuggest) {
                    SuggestScreen(api, imageLoader, suggestViewModel, onBack = { showSuggest = false }, onSignedOut = {
                        showSuggest = false
                        signedIn = false
                    })
                } else if (showOutfits) {
                    OutfitsScreen(api, imageLoader, outfitViewModel, wearViewModel, onHistory = { showWears = true }, onSuggest = { showSuggest = true }, onBack = { showOutfits = false }, onSignedOut = {
                        showOutfits = false
                        signedIn = false
                    })
                } else if (showSettings) {
                    SettingsScreen(api, settingsViewModel, onBack = { showSettings = false }, onSignedOut = {
                        showSettings = false
                        signedIn = false
                    })
                } else {
                    ClosetScreen(api, imageLoader, uploadViewModel, closetViewModel, wearViewModel, onSettings = { showSettings = true }, onOutfits = { showOutfits = true }, onSignedOut = { signedIn = false })
                }
            } else if (showRegistration) {
                RegistrationScreen(
                    store,
                    api,
                    onBack = { showRegistration = false },
                    onSignedIn = { showRegistration = false; signedIn = true },
                )
            } else {
                LoginScreen(store, api, onSignedIn = { signedIn = true }, onCreateAccount = { showRegistration = true })
            }
        }
    }
}

@Composable
private fun SettingsScreen(api: Api, viewModel: SettingsViewModel, onBack: () -> Unit, onSignedOut: () -> Unit) {
    val settings = viewModel.state
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { viewModel.start() }
    LaunchedEffect(settings.unauthorized) {
        if (settings.unauthorized) {
            viewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.Start)) { Text("Back to closet") }
        Text("Settings", fontSize = 28.sp, fontWeight = FontWeight.SemiBold, color = Ink)
        Text("Who is signed in", fontSize = 17.sp, fontWeight = FontWeight.Medium, color = Ink)
        if (settings.loading && settings.user == null) {
            CircularProgressIndicator()
        } else {
            Text(settings.user?.email ?: "Account details unavailable", color = Muted)
        }
        settings.error?.let { Text(it, color = Danger, fontSize = 14.sp) }
        if (settings.user == null && !settings.loading) {
            TextButton(onClick = viewModel::start) { Text("Retry") }
        }

        Text("Display name", fontSize = 17.sp, fontWeight = FontWeight.Medium, color = Ink)
        OutlinedTextField(
            value = settings.displayName,
            onValueChange = viewModel::editDisplayName,
            label = { Text("Display name") },
            singleLine = true,
            enabled = !settings.savingName && settings.user != null,
            isError = settings.nameError != null,
            modifier = Modifier.fillMaxWidth(),
        )
        settings.nameError?.let { Text(it, color = Danger, fontSize = 14.sp) }
        Button(
            onClick = viewModel::saveDisplayName,
            enabled = !settings.savingName && settings.user != null,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (settings.savingName) "Saving..." else "Save display name") }

        Text("Laptop address", fontSize = 17.sp, fontWeight = FontWeight.Medium, color = Ink)
        OutlinedTextField(
            value = settings.laptopAddress,
            onValueChange = viewModel::editLaptopAddress,
            label = { Text("Laptop address") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = viewModel::saveLaptopAddress, modifier = Modifier.fillMaxWidth()) {
            Text(if (settings.addressSaved) "Address saved" else "Save laptop address")
        }

        Text("Cloud address", fontSize = 17.sp, fontWeight = FontWeight.Medium, color = Ink)
        OutlinedTextField(
            value = settings.cloudAddress,
            onValueChange = viewModel::editCloudAddress,
            label = { Text("Cloud address") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = viewModel::saveCloudAddress, modifier = Modifier.fillMaxWidth()) {
            Text(if (settings.addressSaved) "Address saved" else "Save cloud address")
        }
        Text(
            api.lastServerAnswered?.let { "Last request answered by: $it" } ?: "No server has answered yet.",
            color = Muted,
        )

        TextButton(onClick = {
            scope.launch {
                withContext(Dispatchers.IO) { api.logout() }
                onSignedOut()
            }
        }, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text("Sign out") }
    }
}

@Composable
private fun LoginScreen(store: Store, api: Api, onSignedIn: () -> Unit, onCreateAccount: () -> Unit) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(store.baseUrl) }
    var error by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableStateOf(0) }
    var busy by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
    ) {
        Text("OOTD", fontSize = 34.sp, fontWeight = FontWeight.SemiBold, color = Ink)
        Text("Your closet, on your laptop.", fontSize = 15.sp, color = Muted)
        Spacer(Modifier.height(32.dp))

        OutlinedTextField(
            value = email,
            onValueChange = { email = it; error = null },
            label = { Text("Email") },
            singleLine = true,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it; error = null },
            label = { Text("Password") },
            singleLine = true,
            enabled = !busy,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = serverUrl,
            onValueChange = { serverUrl = it; error = null },
            label = { Text("Laptop address") },
            singleLine = true,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        )

        error?.let { message ->
            Spacer(Modifier.height(12.dp))
            Text(message, color = Danger, fontSize = 14.sp)
        }

        Spacer(Modifier.height(24.dp))
        Button(
            onClick = { error = null; busy = true; attempt++ },
            enabled = !busy && email.isNotBlank() && password.isNotBlank(),
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
        ) {
            Text(if (busy) "Signing in..." else "Sign in", fontSize = 16.sp)
        }
        TextButton(onClick = onCreateAccount, enabled = !busy, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text("Create account")
        }
    }

    // Keyed on attempt so a retry after a failure runs again, and a
    // recomposition on its own does not re-fire the request.
    if (busy) {
        LaunchedEffect(attempt) {
            try {
                store.baseUrl = serverUrl
                val token = withContext(Dispatchers.IO) { api.login(email.trim(), password) }
                store.token = token
                onSignedIn()
            } catch (e: Exception) {
                error = e.message ?: "Sign-in failed"
            } finally {
                busy = false
            }
        }
    }
}

@Composable
private fun RegistrationScreen(store: Store, api: Api, onBack: () -> Unit, onSignedIn: () -> Unit) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var displayName by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(store.baseUrl) }
    var emailError by remember { mutableStateOf<String?>(null) }
    var passwordError by remember { mutableStateOf<String?>(null) }
    var confirmError by remember { mutableStateOf<String?>(null) }
    var displayNameError by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var attempt by remember { mutableStateOf(0) }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
    ) {
        Text("Create account", fontSize = 28.sp, fontWeight = FontWeight.SemiBold, color = Ink)
        Text("Start building your closet.", fontSize = 15.sp, color = Muted)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = email,
            onValueChange = { email = it; emailError = null; error = null },
            label = { Text("Email") },
            singleLine = true,
            enabled = !busy,
            isError = emailError != null,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth(),
        )
        emailError?.let { Text(it, color = Danger, fontSize = 12.sp) }
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it; passwordError = null; error = null },
            label = { Text("Password") },
            singleLine = true,
            enabled = !busy,
            isError = passwordError != null,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        passwordError?.let { Text(it, color = Danger, fontSize = 12.sp) }
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = confirmPassword,
            onValueChange = { confirmPassword = it; confirmError = null; error = null },
            label = { Text("Confirm password") },
            singleLine = true,
            enabled = !busy,
            isError = confirmError != null,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        confirmError?.let { Text(it, color = Danger, fontSize = 12.sp) }
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = displayName,
            onValueChange = { displayName = it; displayNameError = null; error = null },
            label = { Text("Display name (optional)") },
            singleLine = true,
            enabled = !busy,
            isError = displayNameError != null,
            modifier = Modifier.fillMaxWidth(),
        )
        displayNameError?.let { Text(it, color = Danger, fontSize = 12.sp) }
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = serverUrl,
            onValueChange = { serverUrl = it; error = null },
            label = { Text("Laptop address") },
            singleLine = true,
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        )
        error?.let { Text(it, color = Danger, fontSize = 14.sp, modifier = Modifier.padding(top = 12.dp)) }
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = {
                emailError = if (!android.util.Patterns.EMAIL_ADDRESS.matcher(email.trim()).matches()) "Enter a valid email address." else null
                passwordError = if (password.length < 10) "Use at least 10 characters." else null
                confirmError = if (confirmPassword != password) "Passwords do not match." else null
                displayNameError = if (displayName.trim().length > 60) "Use 60 characters or fewer." else null
                error = null
                if (emailError == null && passwordError == null && confirmError == null && displayNameError == null) {
                    busy = true
                    attempt++
                }
            },
            enabled = !busy,
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) { Text(if (busy) "Creating account..." else "Create account", fontSize = 16.sp) }
        TextButton(onClick = { store.baseUrl = serverUrl; onBack() }, enabled = !busy, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text("Back to sign in")
        }
    }

    if (busy) {
        LaunchedEffect(attempt) {
            try {
                // Persist the edited laptop address before either request.
                store.baseUrl = serverUrl
                withContext(Dispatchers.IO) { api.signup(email.trim(), password, displayName.trim().ifEmpty { null }) }
                val token = withContext(Dispatchers.IO) { api.login(email.trim(), password) }
                store.token = token
                onSignedIn()
            } catch (e: Exception) {
                val message = e.message ?: "Account creation failed"
                when {
                    message.contains("already registered", ignoreCase = true) -> emailError = message
                    message.startsWith("Check that your email", ignoreCase = true) -> {
                        emailError = "Enter a valid email address."
                        passwordError = "Use at least 10 characters."
                    }
                    else -> error = message
                }
            } finally {
                busy = false
            }
        }
    }
}

@Composable
private fun ClosetScreen(api: Api, imageLoader: ImageLoader, uploadViewModel: UploadViewModel, closetViewModel: ClosetViewModel, wearViewModel: WearViewModel, onSettings: () -> Unit, onOutfits: () -> Unit, onSignedOut: () -> Unit) {
    val closet = closetViewModel.state
    val wearStats = wearViewModel.state.stats
    val scope = rememberCoroutineScope()
    var showAddChoices by remember { mutableStateOf(false) }
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }
    val context = androidx.compose.ui.platform.LocalContext.current
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        val uri = pendingCameraUri
        if (success && uri != null) uploadViewModel.startUpload(uri, context.contentResolver)
    }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) uploadViewModel.startUpload(uri, context.contentResolver)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            val directory = File(context.cacheDir, "camera").apply { mkdirs() }
            val photo = File.createTempFile("closet-", ".jpg", directory)
            pendingCameraUri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photo)
            camera.launch(pendingCameraUri!!)
        } else {
            uploadViewModel.error("Camera permission is needed to take a photo.")
        }
    }

    LaunchedEffect(Unit) { closetViewModel.start(); wearViewModel.start() }

    LaunchedEffect(closet.unauthorized) {
        if (closet.unauthorized) {
            closetViewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }

    LaunchedEffect(wearViewModel.state.unauthorized) {
        if (wearViewModel.state.unauthorized) {
            wearViewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }

    val uploadState = uploadViewModel.state
    if (uploadState !is UploadState.Idle) {
        UploadFlow(uploadState, uploadViewModel, api, imageLoader, onSaved = { saved ->
            // The upload already saved the row; refresh the active server-side filter.
            closetViewModel.setQuery(closet.query)
        }, onDone = { uploadViewModel.dismiss() })
        return
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Three actions beside a 24sp title overflow a 360dp phone, wrapping the
        // title onto two lines, so the actions sit on their own row.
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 20.dp, end = 8.dp, top = 20.dp, bottom = 4.dp),
        ) {
            Text("Your closet", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = Ink)
            closet.items?.let { loaded ->
                Text(
                    if (loaded.size == 1) "1 piece" else "${loaded.size} pieces",
                    fontSize = 14.sp,
                    color = Muted,
                )
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onSettings) { Text("Settings") }
                TextButton(onClick = onOutfits) { Text("Outfits") }
                TextButton(onClick = {
                    scope.launch {
                        withContext(Dispatchers.IO) { api.logout() }
                        onSignedOut()
                    }
                }) { Text("Sign out") }
            }
        }

        Button(
            onClick = { showAddChoices = true },
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        ) { Text("Add piece") }

        OutlinedTextField(
            value = closet.query,
            onValueChange = closetViewModel::setQuery,
            label = { Text("Search by name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        )
        Row(
            modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            listOf("all" to "All", "topwear" to "Topwear", "bottomwear" to "Bottomwear", "shoes" to "Shoes", "accessories" to "Accessories", "other" to "Other").forEach { (value, label) ->
                FilterChip(
                    selected = closet.category == value,
                    onClick = { closetViewModel.selectCategory(value) },
                    label = { Text(label) },
                )
            }
        }

        val loaded = closet.items
        when {
            loaded == null && closet.error != null -> Centered {
                Text(closet.error.orEmpty(), color = Muted, fontSize = 15.sp)
            }

            loaded == null -> Centered { CircularProgressIndicator() }

            loaded.isEmpty() && closet.error != null -> Centered { Text(closet.error.orEmpty(), color = Muted, fontSize = 15.sp) }

            loaded.isEmpty() && (closet.category != "all" || closet.query.isNotBlank()) -> Centered { Text("No pieces match", color = Muted, fontSize = 15.sp) }

            loaded.isEmpty() -> Centered { Text("Nothing here yet", color = Muted, fontSize = 15.sp) }

            else -> LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                contentPadding = PaddingValues(16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(loaded) { item -> GarmentCard(item, api, imageLoader) { closetViewModel.open(item) } }
            }
        }
    }

    if (showAddChoices) {
        AlertDialog(
            onDismissRequest = { showAddChoices = false },
            title = { Text("Add a piece") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        showAddChoices = false
                        if (ContextCompat.checkSelfPermission(context, android.Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                            val directory = File(context.cacheDir, "camera").apply { mkdirs() }
                            val photo = File.createTempFile("closet-", ".jpg", directory)
                            pendingCameraUri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", photo)
                            camera.launch(pendingCameraUri!!)
                        } else permission.launch(android.Manifest.permission.CAMERA)
                    }, modifier = Modifier.fillMaxWidth()) { Text("Take photo") }
                    OutlinedButton(onClick = {
                        showAddChoices = false
                        gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                    }, modifier = Modifier.fillMaxWidth()) { Text("Choose photo") }
                    OutlinedButton(onClick = {
                        showAddChoices = false
                        closetViewModel.openManualEntry()
                    }, modifier = Modifier.fillMaxWidth()) { Text("Enter details") }
                }
            },
            confirmButton = { TextButton(onClick = { showAddChoices = false }) { Text("Cancel") } },
        )
    }

    if (closet.manualEntry) {
        ManualEntrySheet(
            name = closet.manualName,
            category = closet.manualCategory,
            saving = closet.manualSaving,
            error = closet.manualError,
            onNameChange = closetViewModel::editManualName,
            onCategoryChange = closetViewModel::editManualCategory,
            onSave = closetViewModel::saveManual,
            onDismiss = closetViewModel::cancelManualEntry,
        )
    }

    closet.selected?.let { selected ->
        GarmentDetailSheet(
            item = selected,
            name = closet.editName,
            category = closet.editCategory,
            saving = closet.saving,
            error = closet.detailError,
            confirmDelete = closet.confirmDelete,
            wearStats = wearStats,
            api = api,
            imageLoader = imageLoader,
            onNameChange = closetViewModel::editName,
            onCategoryChange = closetViewModel::editCategory,
            onSave = closetViewModel::save,
            onDelete = closetViewModel::askDelete,
            onConfirmDelete = closetViewModel::delete,
            onCancelDelete = closetViewModel::cancelDelete,
            onDismiss = closetViewModel::close,
        )
    }
}

@Composable
private fun OutfitsScreen(api: Api, imageLoader: ImageLoader, viewModel: OutfitViewModel, wearViewModel: WearViewModel, onHistory: () -> Unit, onSuggest: () -> Unit, onBack: () -> Unit, onSignedOut: () -> Unit) {
    val state = viewModel.state
    val wearState = wearViewModel.state
    LaunchedEffect(Unit) { viewModel.start() }
    LaunchedEffect(wearState.notice) {
        wearState.notice?.let {
            viewModel.setWearNotice(it)
            wearViewModel.consumeNotice()
        }
    }
    LaunchedEffect(state.unauthorized) {
        if (state.unauthorized) {
            viewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }
    LaunchedEffect(wearState.unauthorized) {
        if (wearState.unauthorized) {
            wearViewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }

    Column(Modifier.fillMaxSize()) {
        // Back plus two actions beside a 24sp title overflow a 360dp phone and wrap
        // the title onto two lines, so the actions sit on their own row.
        Column(modifier = Modifier.fillMaxWidth().padding(start = 12.dp, end = 16.dp, top = 12.dp, bottom = 4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onBack) { Text("Back") }
                Text("Your outfits", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = Ink)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onSuggest) { Text("Suggest") }
                TextButton(onClick = onHistory) { Text("History") }
            }
        }
        Button(
            onClick = viewModel::openBuilder,
            enabled = !state.saving,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        ) { Text("New outfit") }
        when {
            state.outfits == null && state.error == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            state.outfits == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(state.error.orEmpty(), color = Muted) }
            state.outfits.isEmpty() -> Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                Text(state.error ?: "No saved outfits yet. Create one to get started.", color = Muted)
            }
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                state.error?.let { message -> item { Text(message, color = Danger) } }
                lazyItems(state.outfits) { outfit ->
                    Column(
                        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(14.dp))
                            .clickable { viewModel.open(outfit) }.padding(12.dp),
                    ) {
                        Text(outfit.name, fontSize = 17.sp, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.onSurface)
                        Spacer(Modifier.height(8.dp))
                        Row(
                            Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            outfit.items.forEach { piece -> OutfitPieceTile(piece, api, imageLoader, Modifier.width(76.dp).height(88.dp)) }
                        }
                    }
                }
            }
        }
    }

    state.selected?.let { outfit ->
        OutfitDetailSheet(
            outfit = outfit,
            api = api,
            imageLoader = imageLoader,
            error = state.detailError,
            saving = state.saving,
            confirmDelete = state.confirmDelete,
            wearNotice = state.wearNotice,
            wearError = wearState.error,
            wearSaving = wearState.saving,
            onWear = { outfit -> wearViewModel.recordWear(outfit.items.filter { it.available }.mapNotNull { it.item_id }, outfit.id) },
            onDelete = viewModel::askDelete,
            onConfirmDelete = viewModel::delete,
            onCancelDelete = viewModel::cancelDelete,
            onDismiss = viewModel::close,
        )
    }
    if (state.building) {
        OutfitBuilderSheet(
            state = state,
            api = api,
            imageLoader = imageLoader,
            onNameChange = viewModel::editBuilderName,
            onToggle = viewModel::toggle,
            onSave = viewModel::save,
            onDismiss = viewModel::cancelBuilder,
        )
    }
}

@Composable
private fun SuggestScreen(api: Api, imageLoader: ImageLoader, viewModel: SuggestViewModel, onBack: () -> Unit, onSignedOut: () -> Unit) {
    val state = viewModel.state
    LaunchedEffect(Unit) { viewModel.start() }
    LaunchedEffect(state.unauthorized) {
        if (state.unauthorized) {
            viewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Suggestions", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
        }
        if (state.loading && state.suggestions == null) {
            CircularProgressIndicator()
        } else if (state.error != null) {
            Text(state.error, color = MaterialTheme.colorScheme.error)
            OutlinedButton(onClick = viewModel::refresh, enabled = !state.loading) { Text("Retry") }
        } else {
            val suggestions = state.suggestions.orEmpty()
            val suggestion = suggestions.getOrNull(state.index)
            if (suggestion == null) {
                Text(state.guidance ?: "Add a top and bottom to your wardrobe to get outfit suggestions.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                OutlinedButton(onClick = viewModel::refresh, enabled = !state.loading) { Text(if (state.loading) "Loading..." else "Refresh") }
            } else {
                Row(
                    Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    suggestion.items.forEach { piece ->
                        OutfitPieceTile(
                            OutfitPiece(name = piece.name, image_url = piece.image_url), api, imageLoader,
                            Modifier.width(92.dp).height(108.dp),
                        )
                    }
                }
                Text("${suggestion.score.toInt()} · ${suggestion.verdict}", fontSize = 20.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                suggestion.notes.forEach { note -> Text(note, color = MaterialTheme.colorScheme.onSurfaceVariant) }

                val swatches = suggestion.palette?.palette.orEmpty().mapNotNull { color ->
                    runCatching { color to Color(android.graphics.Color.parseColor(color.hex)) }.getOrNull()
                }
                if (swatches.isNotEmpty()) {
                    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        swatches.forEach { (color, parsed) ->
                            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Box(
                                    Modifier.width(38.dp).height(28.dp).background(parsed, RoundedCornerShape(7.dp))
                                        .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(7.dp)),
                                ) {}
                                Text(color.name ?: color.hex, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                Text("Ranked by colour only; wear history is not used.", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(if (state.onlyOne) "That's the only combination your wardrobe allows." else "${state.index + 1} of ${suggestions.size}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Button(onClick = viewModel::next, enabled = suggestions.size > 1, modifier = Modifier.fillMaxWidth()) { Text("Next") }
                if (state.loading) CircularProgressIndicator()
            }
        }
    }
}

@Composable
private fun OutfitPieceTile(piece: OutfitPiece, api: Api, imageLoader: ImageLoader, modifier: Modifier = Modifier) {
    Box(
        modifier.background(MaterialTheme.colorScheme.surface, RoundedCornerShape(10.dp)).border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (!piece.available) {
            Column(Modifier.padding(4.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Text(piece.name, color = MaterialTheme.colorScheme.onSurface, fontSize = 11.sp, maxLines = 2)
                Text("unavailable", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 10.sp)
            }
        } else if (piece.image_url != null) {
            AsyncImage(
                model = api.imageUrl(piece.image_url), imageLoader = imageLoader, contentDescription = piece.name,
                contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize().padding(5.dp),
            )
        } else {
            Text(piece.name, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 11.sp, modifier = Modifier.padding(4.dp), maxLines = 2)
        }
    }
}

@Composable
private fun WearHistoryScreen(api: Api, imageLoader: ImageLoader, viewModel: WearViewModel, onBack: () -> Unit, onSignedOut: () -> Unit) {
    val state = viewModel.state
    LaunchedEffect(Unit) { viewModel.start() }
    LaunchedEffect(state.unauthorized) {
        if (state.unauthorized) {
            viewModel.consumeUnauthorized()
            withContext(Dispatchers.IO) { api.logout() }
            onSignedOut()
        }
    }
    Column(Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = 12.dp, end = 16.dp, top = 12.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Wear history", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = Ink)
        }
        state.error?.let { Text(it, color = Danger, modifier = Modifier.padding(horizontal = 20.dp)) }
        when {
            state.events == null && state.error == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            state.events.isNullOrEmpty() -> Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                Text(if (state.error == null) "Nothing recorded yet." else state.error.orEmpty(), color = Muted)
            }
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                lazyItems(state.events.orEmpty()) { event ->
                    Column(
                        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(14.dp)).padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Text(event.worn_on ?: event.created_at.take(10), fontSize = 17.sp, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.onSurface)
                        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            event.items.forEach { piece -> OutfitPieceTile(piece, api, imageLoader, Modifier.width(76.dp).height(88.dp)) }
                        }
                        TextButton(onClick = { viewModel.askUndo(event.id) }, enabled = !state.saving, modifier = Modifier.align(Alignment.End)) { Text("Undo") }
                    }
                }
            }
        }
    }
    state.confirmUndo?.let { id ->
        AlertDialog(
            onDismissRequest = viewModel::cancelUndo,
            title = { Text("Undo this wear?") },
            text = { Text("This entry will be removed from your wear history.") },
            confirmButton = { TextButton(onClick = viewModel::undo) { Text("Undo", color = Danger) } },
            dismissButton = { TextButton(onClick = viewModel::cancelUndo) { Text("Cancel") } },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OutfitDetailSheet(
    outfit: Outfit,
    api: Api,
    imageLoader: ImageLoader,
    error: String?,
    wearNotice: String?,
    wearError: String?,
    wearSaving: Boolean,
    onWear: (Outfit) -> Unit,
    saving: Boolean,
    confirmDelete: Boolean,
    onDelete: () -> Unit,
    onConfirmDelete: () -> Unit,
    onCancelDelete: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.fillMaxWidth().heightIn(max = 680.dp).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(outfit.name, fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            outfit.items.forEach { piece ->
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutfitPieceTile(piece, api, imageLoader, Modifier.width(88.dp).height(104.dp))
                    Column {
                        Text(piece.name, color = MaterialTheme.colorScheme.onSurface)
                        if (!piece.available) Text("unavailable", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    }
                }
            }
            error?.let { Text(it, color = Danger, fontSize = 14.sp) }
            val availableItems = outfit.items.filter { it.available }.mapNotNull { it.item_id }
            Button(onClick = { onWear(outfit) }, enabled = !wearSaving && availableItems.isNotEmpty(), modifier = Modifier.fillMaxWidth()) {
                Text(if (wearSaving) "Recording..." else "Wore this today")
            }
            if (availableItems.isEmpty()) Text("No garments left in this outfit.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
            wearNotice?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp) }
            wearError?.let { Text(it, color = Danger, fontSize = 14.sp) }
            OutlinedButton(onClick = onDelete, enabled = !saving, modifier = Modifier.fillMaxWidth()) { Text("Delete", color = Danger) }
            Spacer(Modifier.height(12.dp))
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = onCancelDelete,
            title = { Text("Delete ${outfit.name}?") },
            text = { Text("This saved outfit will be deleted.") },
            confirmButton = { TextButton(onClick = onConfirmDelete) { Text("Delete", color = Danger) } },
            dismissButton = { TextButton(onClick = onCancelDelete) { Text("Cancel") } },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OutfitBuilderSheet(
    state: OutfitState,
    api: Api,
    imageLoader: ImageLoader,
    onNameChange: (String) -> Unit,
    onToggle: (Int) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.fillMaxWidth().heightIn(max = 760.dp).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("New outfit", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
            OutlinedTextField(
                value = state.builderName, onValueChange = onNameChange, label = { Text("Outfit name") },
                singleLine = true, enabled = !state.saving, modifier = Modifier.fillMaxWidth(),
            )
            Text("${state.picked.size} of 8 picked", color = MaterialTheme.colorScheme.onSurfaceVariant)
            state.builderError?.let { Text(it, color = Danger, fontSize = 14.sp) }
            if (state.pickable.isEmpty() && state.builderError == null) {
                Box(Modifier.fillMaxWidth().height(100.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            } else if (state.pickable.isEmpty()) {
                Text("No garments available to choose.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                state.pickable.chunked(2).forEach { rowItems ->
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                        rowItems.forEach { item ->
                            val picked = item.id in state.picked
                            Column(
                                Modifier.weight(1f).border(
                                    width = if (picked) 3.dp else 1.dp,
                                    color = if (picked) Sage else MaterialTheme.colorScheme.outlineVariant,
                                    shape = RoundedCornerShape(12.dp),
                                ).clickable(enabled = !state.saving) { onToggle(item.id) }.padding(7.dp),
                            ) {
                                Box {
                                    GarmentCard(item, api, imageLoader) { onToggle(item.id) }
                                    if (picked) {
                                        Text("✓", color = MaterialTheme.colorScheme.onPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold,
                                            modifier = Modifier.align(Alignment.TopEnd).padding(5.dp).background(Sage, RoundedCornerShape(20.dp)).padding(horizontal = 7.dp, vertical = 2.dp))
                                    }
                                }
                            }
                        }
                        if (rowItems.size == 1) Spacer(Modifier.weight(1f))
                    }
                }
            }
            Button(onClick = onSave, enabled = !state.saving, modifier = Modifier.fillMaxWidth()) {
                Text(if (state.saving) "Saving..." else "Save outfit")
            }
            TextButton(onClick = onDismiss, enabled = !state.saving, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun GarmentCard(item: Item, api: Api, imageLoader: ImageLoader, onClick: () -> Unit) {
    var imageMissing by remember(item.id) { mutableStateOf(false) }
    Column(modifier = Modifier.clickable(onClick = onClick)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(4f / 5f)
                // The cutouts are transparent PNGs: on anything dark the
                // garment disappears.
                .background(Color.White, RoundedCornerShape(14.dp)),
            contentAlignment = Alignment.Center,
        ) {
            if (item.stored_name.isEmpty()) {
                Text("No photo", color = Muted, fontSize = 11.sp)
            } else {
                AsyncImage(
                    model = api.imageUrl(item),
                    imageLoader = imageLoader,
                    contentDescription = item.name,
                    contentScale = ContentScale.Fit,
                    error = ColorPainter(Color.White),
                    placeholder = ColorPainter(Color.White),
                    onError = { imageMissing = true },
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(10.dp),
                )
                if (imageMissing) Text("Image unavailable", color = Muted, fontSize = 11.sp)
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(item.name, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = Ink, maxLines = 1)
        Text(item.category, fontSize = 12.sp, color = Muted)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ManualEntrySheet(
    name: String,
    category: String,
    saving: Boolean,
    error: String?,
    onNameChange: (String) -> Unit,
    onCategoryChange: (String) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Enter details", fontSize = 22.sp, fontWeight = FontWeight.SemiBold, color = Ink)
            OutlinedTextField(
                value = name,
                onValueChange = onNameChange,
                label = { Text("Name") },
                singleLine = true,
                enabled = !saving,
                isError = error != null,
                modifier = Modifier.fillMaxWidth(),
            )
            CategoryPicker(category, onCategoryChange)
            error?.let { Text(it, color = Danger, fontSize = 14.sp) }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onDismiss, enabled = !saving, modifier = Modifier.weight(1f)) { Text("Cancel") }
                Button(
                    onClick = onSave,
                    enabled = !saving && name.isNotBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text(if (saving) "Saving..." else "Save") }
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GarmentDetailSheet(
    item: Item,
    name: String,
    category: String,
    saving: Boolean,
    error: String?,
    confirmDelete: Boolean,
    wearStats: WearStats?,
    api: Api,
    imageLoader: ImageLoader,
    onNameChange: (String) -> Unit,
    onCategoryChange: (String) -> Unit,
    onSave: () -> Unit,
    onDelete: () -> Unit,
    onConfirmDelete: () -> Unit,
    onCancelDelete: () -> Unit,
    onDismiss: () -> Unit,
) {
    var imageMissing by remember(item.id) { mutableStateOf(false) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier.fillMaxWidth().heightIn(max = 680.dp).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(Modifier.fillMaxWidth().height(250.dp).background(Color.White, RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                if (item.stored_name.isEmpty()) {
                    Text("No photo", color = Muted, fontSize = 13.sp)
                } else {
                    AsyncImage(
                        model = api.imageUrl(item),
                        imageLoader = imageLoader,
                        contentDescription = item.name,
                        contentScale = ContentScale.Fit,
                        error = ColorPainter(Color.White),
                        placeholder = ColorPainter(Color.White),
                        onError = { imageMissing = true },
                        modifier = Modifier.fillMaxSize().padding(12.dp),
                    )
                    if (imageMissing) Text("Image unavailable", color = Muted, fontSize = 13.sp)
                }
            }
            OutlinedTextField(value = name, onValueChange = onNameChange, label = { Text("Name") }, singleLine = true, enabled = !saving, modifier = Modifier.fillMaxWidth())
            CategoryPicker(category, onCategoryChange)
            val wearCount = wearStats?.counts?.get(item.id.toString()) ?: 0
            if (wearCount == 0) {
                Text("Not worn yet.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
            } else {
                Text(if (wearCount == 1) "Worn once" else "Worn $wearCount times", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
                wearStats?.last_worn?.get(item.id.toString())?.let { Text("Last worn $it", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp) }
            }
            error?.let { Text(it, color = Danger, fontSize = 14.sp) }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                OutlinedButton(onClick = onDelete, enabled = !saving, modifier = Modifier.weight(1f)) { Text("Delete", color = Danger) }
                Button(onClick = onSave, enabled = !saving && name.isNotBlank(), modifier = Modifier.weight(1f)) { Text(if (saving) "Saving..." else "Save") }
            }
            Spacer(Modifier.height(12.dp))
        }
    }
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = onCancelDelete,
            title = { Text("Delete ${item.name}?") },
            text = { Text("This piece will be permanently removed from your closet.") },
            confirmButton = { TextButton(onClick = onConfirmDelete) { Text("Delete", color = Danger) } },
            dismissButton = { TextButton(onClick = onCancelDelete) { Text("Cancel") } },
        )
    }
}

@Composable
private fun UploadFlow(
    state: UploadState,
    viewModel: UploadViewModel,
    api: Api,
    imageLoader: ImageLoader,
    onSaved: (Item) -> Unit,
    onDone: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    when (state) {
        UploadState.Idle -> Unit
        is UploadState.Uploading -> Column(
            modifier = Modifier.fillMaxSize().padding(28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            CircularProgressIndicator()
            Spacer(Modifier.height(24.dp))
            Text(state.message, fontSize = 19.sp, fontWeight = FontWeight.Medium, color = Ink)
            Spacer(Modifier.height(8.dp))
            Text("This can take about a minute. Your photo is being processed on the laptop.", color = Muted)
            Spacer(Modifier.height(12.dp))
            Text("${state.seconds}s", color = Muted, fontSize = 13.sp)
        }
        is UploadState.Review -> Column(Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Review pieces", fontSize = 24.sp, fontWeight = FontWeight.SemiBold, color = Ink)
                    Text("${state.candidates.size} found", color = Muted, fontSize = 14.sp)
                }
                TextButton(onClick = onDone) { Text("Cancel") }
            }
            state.notice?.let { Text(it, color = Muted, modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp)) }
            androidx.compose.foundation.lazy.LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.candidates.size) { index ->
                    val candidate = state.candidates[index]
                    Row(
                        modifier = Modifier.fillMaxWidth().background(Color.White, RoundedCornerShape(14.dp)).padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        AsyncImage(
                            model = api.imageUrl(candidate.image_url),
                            imageLoader = imageLoader,
                            contentDescription = candidate.name,
                            contentScale = ContentScale.Fit,
                            modifier = Modifier.width(92.dp).height(112.dp).background(Color.White),
                        )
                        Column(Modifier.weight(1f)) {
                            OutlinedTextField(
                                value = candidate.name,
                                onValueChange = { viewModel.editCandidate(index, candidate.copy(name = it)) },
                                label = { Text("Name") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Spacer(Modifier.height(6.dp))
                            CategoryPicker(candidate.category) { viewModel.editCandidate(index, candidate.copy(category = it)) }
                            candidate.confidence?.let {
                                Text("${(it * 100).toInt()}% match", color = Muted, fontSize = 12.sp)
                            }
                            TextButton(onClick = { viewModel.removeCandidate(index) }) {
                                Text("Remove", color = Danger)
                            }
                        }
                    }
                }
            }
            Button(
                onClick = { scope.launch { viewModel.save(onSaved) } },
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth().padding(16.dp).height(52.dp),
            ) { Text("Save ${state.candidates.size} ${if (state.candidates.size == 1) "piece" else "pieces"}") }
        }
        is UploadState.Saving -> Centered {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text(if (state.remaining == 0) "Finishing up..." else "Saving pieces... ${state.remaining} left", color = Ink)
            }
        }
        is UploadState.Empty -> Column(
            modifier = Modifier.fillMaxSize().padding(28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("No pieces to review", fontSize = 22.sp, fontWeight = FontWeight.SemiBold, color = Ink)
            Spacer(Modifier.height(12.dp))
            Text(state.notice ?: "Try a different photo.", color = Muted)
            Spacer(Modifier.height(24.dp))
            Button(onClick = onDone) { Text("Back to closet") }
        }
        is UploadState.Failed -> Column(
            modifier = Modifier.fillMaxSize().padding(28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Could not finish", fontSize = 22.sp, fontWeight = FontWeight.SemiBold, color = Ink)
            Spacer(Modifier.height(12.dp))
            Text(state.message, color = Muted)
            Spacer(Modifier.height(24.dp))
            Button(onClick = onDone) { Text("Back to closet") }
        }
    }
}

@Composable
private fun CategoryPicker(category: String, onSelected: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }) { Text(category) }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            listOf("topwear", "bottomwear", "shoes", "accessories", "other").forEach { option ->
                DropdownMenuItem(text = { Text(option) }, onClick = { expanded = false; onSelected(option) })
            }
        }
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { content() }
}
