package com.wardrobe.ootd

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ClosetState(
    val items: List<Item>? = null,
    val category: String = "all",
    val query: String = "",
    val selected: Item? = null,
    val editName: String = "",
    val editCategory: String = "other",
    val confirmDelete: Boolean = false,
    val saving: Boolean = false,
    val detailError: String? = null,
    val manualEntry: Boolean = false,
    val manualName: String = "",
    val manualCategory: String = "other",
    val manualSaving: Boolean = false,
    val manualError: String? = null,
    val error: String? = null,
    val unauthorized: Boolean = false,
)

class ClosetViewModel(private val api: Api) : ViewModel() {
    var state by mutableStateOf(ClosetState())
        private set

    private var searchJob: Job? = null
    private var loadJob: Job? = null

    /**
     * Called when the closet becomes visible, never from `init`. This
     * ViewModel is created with the Activity and outlives sign-out, so
     * loading at construction fired an unauthenticated request, latched
     * [ClosetState.unauthorized], and signed the user back out the instant
     * they signed in.
     */
    fun start() {
        state = state.copy(error = null)
        load()
    }

    /** Clears the flag as it is acted on, so a later sign-in is not bounced. */
    fun consumeUnauthorized() {
        state = state.copy(unauthorized = false)
    }

    fun selectCategory(category: String) {
        if (state.category == category) return
        state = state.copy(category = category, error = null)
        searchJob?.cancel()
        load()
    }

    fun setQuery(query: String) {
        state = state.copy(query = query, error = null)
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(300)
            load()
        }
    }

    private fun load() {
        loadJob?.cancel()
        val category = state.category
        val query = state.query.trim()
        loadJob = viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { api.items(category, query) }
                if (category == state.category && query == state.query.trim()) {
                    state = state.copy(items = result, error = null)
                }
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not load your closet")
            }
        }
    }

    fun open(item: Item) {
        state = state.copy(selected = item, editName = item.name, editCategory = item.category, detailError = null, confirmDelete = false)
    }

    fun close() { state = state.copy(selected = null, confirmDelete = false, detailError = null) }
    fun openManualEntry() {
        state = state.copy(manualEntry = true, manualName = "", manualCategory = "other", manualError = null)
    }
    fun cancelManualEntry() {
        if (!state.manualSaving) state = state.copy(manualEntry = false, manualError = null)
    }
    fun editManualName(value: String) { state = state.copy(manualName = value, manualError = null) }
    fun editManualCategory(value: String) { state = state.copy(manualCategory = value, manualError = null) }

    fun saveManual() {
        if (state.manualSaving) return
        val name = state.manualName.trim()
        if (name.isEmpty()) {
            state = state.copy(manualError = "Enter a name for this piece.")
            return
        }
        if (name.length > 120) {
            state = state.copy(manualError = "Use 120 characters or fewer.")
            return
        }
        state = state.copy(manualSaving = true, manualError = null)
        viewModelScope.launch {
            try {
                val saved = withContext(Dispatchers.IO) { api.createManualItem(name, state.manualCategory) }
                val matches = (state.category == "all" || state.category == saved.category) &&
                    (state.query.isBlank() || saved.name.contains(state.query.trim(), ignoreCase = true))
                state = state.copy(
                    items = if (matches) listOf(saved) + state.items.orEmpty().filterNot { it.id == saved.id } else state.items,
                    manualEntry = false,
                )
                load()
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true, manualError = "Session expired")
            } catch (e: Exception) {
                state = state.copy(manualError = e.message ?: "Could not save this piece")
            } finally {
                state = state.copy(manualSaving = false)
            }
        }
    }
    fun editName(value: String) { state = state.copy(editName = value) }
    fun editCategory(value: String) { state = state.copy(editCategory = value) }
    fun askDelete() { state = state.copy(confirmDelete = true) }
    fun cancelDelete() { state = state.copy(confirmDelete = false) }

    fun save() {
        val item = state.selected ?: return
        if (state.saving) return
        state = state.copy(saving = true, detailError = null)
        viewModelScope.launch {
            try {
                val updated = withContext(Dispatchers.IO) { api.updateItem(item.id, state.editName.trim(), state.editCategory) }
                if (updated == null) {
                    drop(item.id)
                } else {
                    state = state.copy(
                        items = state.items?.map { if (it.id == updated.id) updated else it },
                        selected = updated,
                        editName = updated.name,
                        editCategory = updated.category,
                    )
                    load()
                }
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true, detailError = "Session expired")
            } catch (e: Exception) {
                state = state.copy(detailError = e.message ?: "Could not update this piece")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }

    fun delete() {
        val item = state.selected ?: return
        if (state.saving) return
        state = state.copy(saving = true, detailError = null, confirmDelete = false)
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { api.deleteItem(item.id) }
                drop(item.id)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true, detailError = "Session expired")
            } catch (e: Exception) {
                state = state.copy(detailError = e.message ?: "Could not delete this piece")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }

    private fun drop(id: Int) {
        state = state.copy(items = state.items?.filterNot { it.id == id }, selected = null, confirmDelete = false)
    }
}

class ClosetViewModelFactory(private val api: Api) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(ClosetViewModel::class.java)) return ClosetViewModel(api) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
