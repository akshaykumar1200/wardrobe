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
import java.time.LocalDate

data class WearState(
    val events: List<WearEvent>? = null,
    val stats: WearStats? = null,
    val error: String? = null,
    val unauthorized: Boolean = false,
    val saving: Boolean = false,
    val confirmUndo: Int? = null,
    val notice: String? = null,
)

class WearViewModel(private val api: Api) : ViewModel() {
    var state by mutableStateOf(WearState())
        private set

    fun start() {
        state = state.copy(error = null)
        viewModelScope.launch {
            try {
                val (events, stats) = withContext(Dispatchers.IO) { api.wears() to api.wearStats() }
                state = state.copy(events = events, stats = stats, error = null)
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not load wear history")
            }
        }
    }

    fun consumeUnauthorized() { state = state.copy(unauthorized = false) }

    fun recordWear(itemIds: List<Int>, outfitId: Int?) {
        if (state.saving || itemIds.isEmpty()) return
        state = state.copy(saving = true, error = null, notice = null)
        viewModelScope.launch {
            try {
                val event = withContext(Dispatchers.IO) {
                    api.recordWear(itemIds, outfitId, LocalDate.now().toString())
                }
                state = state.copy(notice = if (event.already_recorded) "Already recorded today" else "Recorded for today")
                reload()
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not record this wear")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }

    fun askUndo(id: Int) { if (!state.saving) state = state.copy(confirmUndo = id) }
    fun cancelUndo() { state = state.copy(confirmUndo = null) }

    fun undo() {
        val id = state.confirmUndo ?: return
        if (state.saving) return
        state = state.copy(saving = true, confirmUndo = null, error = null)
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { api.deleteWear(id) }
                reload()
            } catch (e: Unauthorized) {
                state = state.copy(unauthorized = true)
            } catch (e: Exception) {
                state = state.copy(error = e.message ?: "Could not undo this wear")
            } finally {
                state = state.copy(saving = false)
            }
        }
    }

    fun consumeNotice() { state = state.copy(notice = null) }

    private suspend fun reload() {
        try {
            val (events, stats) = withContext(Dispatchers.IO) { api.wears() to api.wearStats() }
            state = state.copy(events = events, stats = stats, error = null)
        } catch (e: Unauthorized) {
            state = state.copy(unauthorized = true)
        } catch (e: Exception) {
            state = state.copy(error = e.message ?: "Could not refresh wear history")
        }
    }
}

class WearViewModelFactory(private val api: Api) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(WearViewModel::class.java)) return WearViewModel(api) as T
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
