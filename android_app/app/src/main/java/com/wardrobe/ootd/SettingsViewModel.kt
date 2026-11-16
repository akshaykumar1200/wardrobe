package com.wardrobe.ootd

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class SettingsState(
    val user: UserProfile? = null,
    val displayName: String = "",
    val laptopAddress: String = "",
    val cloudAddress: String = "",
    val loading: Boolean = false,
    val savingName: Boolean = false,
    val addressSaved: Boolean = false,
    val error: String? = null,
    val nameError: String? = null,
    val unauthorized: Boolean = false,
)

class SettingsViewModel(private val api: Api, private val store: Store) : ViewModel() {
    var state by mutableStateOf(SettingsState(laptopAddress = store.baseUrl, cloudAddress = store.cloudUrl))
        private set

    fun start() {
        if (state.loading) return
        state = state.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val user = withContext(Dispatchers.IO) { api.currentUser() }
                state = state.copy(user = user, displayName = user.display_name.orEmpty(), error = null)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not load your account")
            } finally {
                state = state.copy(loading = false)
            }
        }
    }

    fun consumeUnauthorized() { state = state.copy(unauthorized = false) }

    fun editDisplayName(value: String) {
        state = state.copy(displayName = value, nameError = null, error = null)
    }

    fun editLaptopAddress(value: String) {
        state = state.copy(laptopAddress = value, addressSaved = false, error = null)
    }

    fun editCloudAddress(value: String) {
        state = state.copy(cloudAddress = value, addressSaved = false, error = null)
    }

    fun saveLaptopAddress() {
        val address = state.laptopAddress.trim().trimEnd('/')
        if (address.isBlank()) {
            state = state.copy(error = "Enter your laptop address.", addressSaved = false)
            return
        }
        store.baseUrl = address
        api.forgetServer()
        state = state.copy(laptopAddress = store.baseUrl, addressSaved = true, error = null)
        start()
    }

    fun saveCloudAddress() {
        store.cloudUrl = state.cloudAddress
        api.forgetServer()
        state = state.copy(cloudAddress = store.cloudUrl, addressSaved = true, error = null)
        start()
    }

    fun saveDisplayName() {
        if (state.savingName) return
        val name = state.displayName.trim()
        if (name.isEmpty() || name.length > 60) {
            state = state.copy(nameError = "Use 1 to 60 characters after trimming.")
            return
        }
        state = state.copy(savingName = true, nameError = null, error = null)
        viewModelScope.launch {
            try {
                val user = withContext(Dispatchers.IO) { api.updateDisplayName(name) }
                state = state.copy(user = user, displayName = user.display_name.orEmpty())
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(nameError = e.message ?: "Could not update your display name")
            } finally {
                state = state.copy(savingName = false)
            }
        }
    }
}

class SettingsViewModelFactory(private val api: Api, private val store: Store) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(SettingsViewModel::class.java)) return SettingsViewModel(api, store) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
